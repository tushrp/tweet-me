"""
One-time script. Generates an intro/announcement tweet via LLM,
sends to Telegram for approval, then posts on approval.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import config
import telegram_bot
import twitter
from openai import OpenAI

persona = config.PERSONA_PATH.read_text()
client = OpenAI(api_key=config.OPENAI_API_KEY)

sig_reserved = (len(config.TWEET_SIGNATURE) + 2) if config.TWEET_SIGNATURE else 0
max_chars = 280 - sig_reserved

response = client.chat.completions.create(
    model=config.OPENAI_MODEL_DRAFT,
    response_format={"type": "json_object"},
    messages=[
        {
            "role": "system",
            "content": f"""{persona}

this is your very first tweet from this account in the new voice.
write 2-3 candidate intro tweets. announce that you're starting to post your dev journey here — commits, projects, the slow grind.
keep it simple, honest, and in character.

hard rules:
- max {max_chars} chars
- first person only
- lowercase, no hashtags, no emojis

return valid JSON only:
{{"drafts": [{{"tweet": "<text>", "confidence": <0.0-1.0>, "angle": "<short phrase>"}}]}}""",
        },
        {
            "role": "user",
            "content": "write the intro tweet(s).",
        },
    ],
    temperature=1.0,
)

data = json.loads(response.choices[0].message.content)


def _apply_signature(text: str) -> str:
    if config.TWEET_SIGNATURE:
        return f"{text}\n\n{config.TWEET_SIGNATURE}"
    return text


drafts = []
for d in data.get("drafts", []):
    text = d.get("tweet", "").strip()
    if text and len(text) <= max_chars:
        drafts.append({
            "tweet": _apply_signature(text),
            "confidence": d.get("confidence", 0.9),
            "angle": d.get("angle", "intro"),
        })

if not drafts:
    print("LLM returned no valid drafts. try again.")
    sys.exit(1)

telegram_bot.send_drafts(drafts)
print(f"sent {len(drafts)} intro draft(s) to Telegram. approve one to go live.")
