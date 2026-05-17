import json
import os
from dataclasses import dataclass

from openai import OpenAI

import config
from github_fetch import Commit, summarize_for_llm

_client = OpenAI(api_key=config.OPENAI_API_KEY)


@dataclass
class Draft:
    tweet: str
    confidence: float
    angle: str


def _load_persona() -> str:
    env_persona = os.environ.get("PERSONA_CONTENT")
    if env_persona:
        return env_persona
    return config.PERSONA_PATH.read_text()


def generate_drafts(
    commits: list[Commit],
    recent_tweets: list[dict],
) -> list[Draft]:
    persona = _load_persona()
    commit_summary = summarize_for_llm(commits)
    recent = "\n".join(f"- {t['text']}" for t in recent_tweets) or "none yet"

    repos_today = sorted(set(c.repo for c in commits))
    project_list = ", ".join(repos_today) if repos_today else "none"

    header = "dev log:"

    max_chars = 280 - (len(config.TWEET_SIGNATURE) + 2 if config.TWEET_SIGNATURE else 0)

    system = f"""{persona}

tweet header (MUST be the first line of the tweet, exactly as shown): {header}

projects with commits today: {project_list}
you MUST write one line for EACH of these projects. do NOT mention any project not in this list.

STEP 1 — synthesize, do not pick:
for each project, read ALL of today's commit messages and file paths TOGETHER as a group.
ask yourself: "if a friend asked what I did on this project today, what would I say in one sentence?"
that sentence is the story. it is almost never the title of a single commit.

how to synthesize:
- look for the through-line. what connects these commits? a deployment? a new capability? fixing a class of bugs? a rewrite?
- multiple small commits around the same files = one bigger change in progress.
- mixed bag of unrelated commits = pick the single most impactful one and lead with it.
- a fresh setup commit + many follow-ups = the setup is the story, the follow-ups are details.
- a "fix" or "tweak" commit on top of a major change earlier today = the major change is still the story.

worked examples:
- ["fix login redirect", "fix login redirect again", "add error toast on login"] → "rewrote the login flow — it was silently failing in 3 different ways"
- ["wip", "wip", "merge auth branch"] → "shipped auth — users can finally log in with google"
- ["bump deps", "bump deps", "fix breaking change in stripe sdk"] → "updated stripe to v9 — their new webhook signing broke our handler"
- ["add parser for X", "add parser for Y", "register both in pipeline"] → "expanded the parser to handle two new transaction types from my bank"

STEP 2 — translate to plain english:
strip every term a non-coder wouldn't know. translate or drop it.
- "deferred imports" → "faster cold starts" or just don't mention
- "read-only filesystem" → "the host doesn't let me write files"
- "cron job" → "scheduled task"
- "oauth refresh" → "re-login flow"
- "schema migration" → "database changes"
if you can't translate it cleanly, the detail probably doesn't belong in the tweet. zoom out.

post when: something shipped today.
skip when: no commits today.
never repeat the same angle as recent posts.

generate 1-3 candidate tweets. if nothing to post, return should_post=false with empty drafts.

hard rules:
- TOTAL tweet (header + all project lines) must be <= {max_chars} characters. count as you write.
- with N projects, each project line must fit in roughly ({max_chars} - 20) / N characters. for 2 projects that is ~130 chars per line.
- lowercase only
- no hashtags, no emojis

return valid JSON only:
{{"should_post": true/false, "drafts": [{{"tweet": "<text>", "confidence": <0.0-1.0>, "angle": "<projects covered>"}}]}}"""

    user = f"commits today:\n{commit_summary}\n\nrecent posts:\n{recent}"

    response = _client.chat.completions.create(
        model=config.OPENAI_MODEL_DRAFT,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=1.0,
    )

    import logging
    logger = logging.getLogger(__name__)

    data = json.loads(response.choices[0].message.content)
    logger.info(f"llm raw response: {data}")
    if not data.get("should_post", True):
        return []

    drafts = []
    for d in data.get("drafts", []):
        tweet_text = d.get("tweet", "").strip()
        confidence = float(d.get("confidence", 0.5))
        logger.info(f"draft candidate: confidence={confidence} angle={d.get('angle')} tweet={tweet_text!r} len={len(tweet_text)}")
        if not tweet_text:
            continue
        if len(tweet_text) > 280:
            tweet_text = _shorten_to_limit(tweet_text, 280)
            logger.info(f"trimmed overflow draft to {len(tweet_text)} chars: {tweet_text!r}")
        drafts.append(Draft(
            tweet=tweet_text,
            confidence=confidence,
            angle=d.get("angle", ""),
        ))

    drafts.sort(key=lambda d: d.confidence, reverse=True)
    return drafts[:3]


def _shorten_to_limit(text: str, limit: int) -> str:
    """Trim each project line's '— why' clause until the whole tweet fits."""
    if len(text) <= limit:
        return text
    lines = text.split("\n")
    while len(text) > limit:
        cut_idx = None
        for i, line in enumerate(lines):
            if " — " in line:
                cut_idx = i
                break
        if cut_idx is None:
            break
        lines[cut_idx] = lines[cut_idx].split(" — ")[0].rstrip(" .") + "."
        text = "\n".join(lines)
    if len(text) > limit:
        text = text[: limit - 1].rstrip() + "…"
    return text
