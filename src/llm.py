import json
import os
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
    env_persona = os.environ.get("PERSONA_CONTENT")
    if env_persona:
        return env_persona
    return config.PERSONA_PATH.read_text()


def decide(commits: list[Commit], recent_tweets: list[dict], stale_repos: list[StaleRepo] | None = None) -> Decision:
    commit_summary = summarize_for_llm(commits, stale_repos)
    recent = "\n".join(f"- {t['text']}" for t in recent_tweets) or "none yet"

    system = f"""you decide whether {config.BOT_OWNER_NAME} should tweet today based on his git activity and unfinished projects.
the tweet will be written in his first person voice ("I", "me", "my").

post when: something shipped, a streak is building, an old project deserves a nudge, the stats tell a story, or there's a dry technical observation worth making.
skip when: nothing happened and there's literally nothing honest to say.

post roughly 5 days out of 7. silence is fine but don't go quiet too often.
never repeat the same vibe as recent posts.

mood vocabulary: shipped, stats, receipt, nudge, streak, slow, dry, win

return valid JSON only:
{{"should_post": true/false, "mood": "<mood>", "reasoning": "<one sentence>"}}"""

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

write 1-3 candidate tweets in {config.BOT_OWNER_NAME}'s own first person voice.
use real numbers, file counts, line counts, tech specifics from the commits.
let the data and tech details carry the humor.
mention his own unfinished projects when relevant — like talking about himself.

hard rules:
- max {280 - (len(config.TWEET_SIGNATURE) + 2 if config.TWEET_SIGNATURE else 0)} characters each
- lowercase only
- no hashtags, no emojis
- simple words only — no jargon dump or big vocabulary
- FIRST PERSON ONLY — "I", "me", "my", "we". never use "he", "him", or his name in third person.
- dry, self-aware humor through facts and stats. not roast, not mean.

don't repeat the vibe of recent posts.

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
