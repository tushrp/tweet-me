"""
One-time script. Generates the AI takeover announcement via LLM,
sends to Telegram for approval, then posts on approval.
Run once before starting the nightly pipeline.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import config
import storage
import telegram_bot
from openai import OpenAI

recent = storage.get_recent_posted_tweets(days=365)
if any("officially taken over" in t["text"] for t in recent):
    print("intro already posted. AI Tushar is live.")
    sys.exit(0)

persona = config.PERSONA_PATH.read_text()
client = OpenAI(api_key=config.OPENAI_API_KEY)

response = client.chat.completions.create(
    model=config.OPENAI_MODEL_DRAFT,
    response_format={"type": "json_object"},
    messages=[
        {
            "role": "system",
            "content": f"""{persona}

this is your very first tweet. you are announcing that you have taken over {config.BOT_OWNER_HANDLE}'s account.
write 2-3 candidate intro/takeover tweets. make it feel like a hostile (but funny) AI takeover.
establish who you are, what you're here to do, and what {config.BOT_OWNER_NAME}'s problem is.
can be slightly longer than usual — this is your origin story.

return valid JSON only:
{{"drafts": [{{"tweet": "<text>", "confidence": <0.0-1.0>, "angle": "<short phrase>"}}]}}""",
        },
        {
            "role": "user",
            "content": "write the takeover announcement tweet(s).",
        },
    ],
    temperature=1.0,
)

data = json.loads(response.choices[0].message.content)
drafts = []
for d in data.get("drafts", []):
    text = d.get("tweet", "").strip()
    if text and len(text) <= 280:
        drafts.append({"tweet": text, "confidence": d.get("confidence", 0.9), "angle": d.get("angle", "intro")})

if not drafts:
    print("LLM returned no valid drafts. try again.")
    sys.exit(1)

draft_ids = storage.save_pending_drafts(drafts, [])
telegram_bot.send_drafts(drafts, draft_ids)
print(f"sent {len(drafts)} intro draft(s) to Telegram. approve one to go live.")
