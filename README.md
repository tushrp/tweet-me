# tweet-me

an AI that takes over your X account and posts your daily dev progress — based on your real GitHub commits.

it decides what to tweet. it decides whether to tweet. you just approve.

---

## the idea

most dev twitter accounts are either dead or full of hot takes.

this bot fixes the first problem. it monitors your GitHub activity every night, drafts a tweet in your voice, sends it to you on telegram, and waits for approval. if nothing interesting happened, it stays silent.

the character is an AI that has "taken over" your account — it roasts you when you procrastinate, celebrates when you ship, and keeps receipts on your unfinished projects.

---

## how it works

```
2:30 AM cron
  → fetch commits from last 24h (public + private repos)
  → fetch stale repos (your unfinished project debt)
  → LLM pass 1: should we post? what's the mood?
  → LLM pass 2: draft 1-3 candidate tweets
  → send to Telegram with approval buttons

you wake up, pick a tweet (or edit it), tap ✅
  → posts to X immediately
```

---

## setup

### 1. clone and install

```bash
git clone https://github.com/yourusername/tweet-me
cd tweet-me
pip install -e .
```

### 2. configure

```bash
cp .env.example .env
```

fill in `.env` — you'll need:

| var | where to get it |
|-----|----------------|
| `GITHUB_TOKEN` | github.com/settings/tokens — `repo` scope |
| `OPENAI_API_KEY` | platform.openai.com/api-keys |
| `TELEGRAM_BOT_TOKEN` | @BotFather on Telegram |
| `TELEGRAM_CHAT_ID` | @userinfobot on Telegram |
| `TWITTER_CLIENT_ID` + `TWITTER_CLIENT_SECRET` | developer.twitter.com → your app → OAuth 2.0 |
| `TWITTER_*` keys | developer.twitter.com → Keys and Tokens |

### 3. set your persona

```bash
cp src/persona.md.example src/persona.md
```

edit `src/persona.md` to describe your voice. this is the prompt the LLM uses to write in your style. `persona.md` is gitignored — it stays on your machine.

### 4. authorize Twitter

```bash
python scripts/auth_twitter.py
```

opens a browser, you authorize, tokens are saved to `.env` automatically.

> note: X API requires a paid developer account ($5 prepaid credit is enough for a full year of daily tweets).

### 5. introduce yourself

```bash
python scripts/introduce.py
```

generates the AI takeover announcement, sends to Telegram. approve it to go live.

### 6. run

two processes:

```bash
# terminal 1 — listens for your telegram approvals (keep running)
python scripts/run_bot.py

# terminal 2 — run once to test the nightly pipeline
python scripts/run_nightly.py
```

for production, run both on a VPS or Railway with a cron at 2:30 AM.

---

## project structure

```
src/
  main.py          — nightly pipeline orchestrator
  github_fetch.py  — fetch commits + stale repos via GitHub API
  llm.py           — two-pass LLM: decide → draft
  telegram_bot.py  — send drafts, handle approvals
  twitter.py       — post via Twitter API v2
  storage.py       — sqlite (tweets, decisions)
  config.py        — env loading
  persona.md       — your voice prompt (gitignored, create from .example)

scripts/
  run_nightly.py   — cron entry point
  run_bot.py       — telegram bot listener
  introduce.py     — one-time takeover announcement
  auth_twitter.py  — one-time Twitter OAuth2 setup
  expire_drafts.py — mark unapproved drafts as expired
```

---

## cron setup (production)

```
# 2:30 AM nightly analysis
30 2 * * * cd /path/to/tweet-me && python scripts/run_nightly.py

# noon expiry check
0 12 * * * cd /path/to/tweet-me && python scripts/expire_drafts.py
```

run `scripts/run_bot.py` as a persistent service (systemd or Railway).

---

## stack

- python 3.11+
- openai (gpt-4o for drafts, gpt-4o-mini for decide pass)
- python-telegram-bot
- PyGithub
- sqlite (no external db needed)
- tweepy + requests (Twitter API v2)

---

## future

- reply to your own tweets as the AI character
- ingest non-git signals (calendar, terminal history)
- learn from approvals/rejections to improve taste over time
