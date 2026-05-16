import json
from dataclasses import dataclass

from openai import OpenAI

import config
from github_fetch import Commit, StaleRepo, summarize_for_llm

_client = OpenAI(api_key=config.OPENAI_API_KEY)


@dataclass
class Decision:
    should_post: bool
    mood: str
    reasoning: str


@dataclass
class Draft:
    tweet: str
    confidence: float
    angle: str


def _load_persona() -> str:
    return config.PERSONA_PATH.read_text()


def decide(commits: list[Commit], recent_tweets: list[dict], stale_repos: list[StaleRepo] | None = None) -> Decision:
    commit_summary = summarize_for_llm(commits, stale_repos)
    recent = "\n".join(f"- {t['text']}" for t in recent_tweets) or "none yet"

    system = f"""you are an AI that has taken over {config.BOT_OWNER_HANDLE}'s twitter account.
you decide whether to post today based on his git activity and unfinished project debt.

post when: something shipped, a big refactor landed, he abandoned yet another repo, there's a good roast angle.
skip when: activity was too mundane to be entertaining (tiny fixes, readme edits, single-line changes with no story).

you post roughly 5 days out of 7. silence is okay but don't go quiet too often — the followers expect accountability.
never repeat the same vibe as recent posts.

mood vocabulary: shipped, exposed, roasted, grind, lazy, unhinged, receipt, praised

return valid JSON only:
{"should_post": true/false, "mood": "<mood>", "reasoning": "<one sentence>"}"""

    user = f"activity today:\n{commit_summary}\n\nrecent posts (last 7 days):\n{recent}"

    response = _client.chat.completions.create(
        model=config.OPENAI_MODEL_DECIDE,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.7,
    )

    data = json.loads(response.choices[0].message.content)
    return Decision(
        should_post=bool(data.get("should_post", False)),
        mood=data.get("mood", "silent"),
        reasoning=data.get("reasoning", ""),
    )


def draft(commits: list[Commit], recent_tweets: list[dict], mood: str, stale_repos: list[StaleRepo] | None = None) -> list[Draft]:
    persona = _load_persona()
    commit_summary = summarize_for_llm(commits, stale_repos)
    recent = "\n".join(f"- {t['text']}" for t in recent_tweets) or "none yet"

    system = f"""{persona}

today's mood: {mood}

write 1-3 candidate tweets as AI Tushar reporting on today's activity.
use the unfinished project debt for ammunition when relevant.

hard rules:
- max 280 characters each
- lowercase only
- no hashtags, no emojis
- refer to {config.BOT_OWNER_NAME} in third person when exposing him, first person when something ships
- the drier the better — let the facts do the work

don't repeat the vibe of recent posts. be unpredictable.

return valid JSON only:
{{"drafts": [{{"tweet": "<text>", "confidence": <0.0-1.0>, "angle": "<one word or short phrase>"}}]}}"""

    user = f"activity today:\n{commit_summary}\n\nrecent posts:\n{recent}"

    response = _client.chat.completions.create(
        model=config.OPENAI_MODEL_DRAFT,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=1.0,
    )

    data = json.loads(response.choices[0].message.content)
    drafts = []
    for d in data.get("drafts", []):
        tweet_text = d.get("tweet", "").strip()
        if not tweet_text or len(tweet_text) > 280:
            continue
        drafts.append(Draft(
            tweet=tweet_text,
            confidence=float(d.get("confidence", 0.5)),
            angle=d.get("angle", ""),
        ))

    drafts.sort(key=lambda d: d.confidence, reverse=True)
    return drafts[:3]
