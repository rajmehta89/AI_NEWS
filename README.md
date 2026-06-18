# Daily AI/ML News Agent (Claude-powered)

A Python agent that every morning:
1. **Gathers** worldwide AI/ML news from the last 24h (15 free RSS sources).
2. **Reads it with Claude** — Claude drops noise/duplicates, writes a clean one-line
   summary for each story, ranks by importance, groups by topic, and **separates
   stock-market items from real AI news**.
3. **Emails you TWO digests:**
   - 🗞️ **Daily AI Newspaper** — the AI/ML news
   - 📈 **Daily AI Stock & Market Watch** — AI stock/market items (separate email)

If Claude is turned off or unavailable, it falls back to a single plain RSS email.

---

## What's required

| Requirement | Why | Cost |
|---|---|---|
| **Python 3** (installed: 3.14) | Runs the agent | free |
| **feedparser** + **anthropic** | Read feeds + call Claude (`pip install -r requirements.txt`) | free |
| **Gmail App Password** | So the script can send the emails | free |
| **Anthropic API key** | So Claude can edit/summarize/split the news | ~pennies/day (see below) |

---

## Setup (one time)

1. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

2. **Gmail App Password** (for sending):
   - Turn on 2-Step Verification, then go to https://myaccount.google.com/apppasswords
   - Create one, copy the 16-character code.

3. **Anthropic API key** (for Claude):
   - Get it from https://console.anthropic.com → API Keys.

4. **Edit `config.json`:**
   - `send_to` → who receives the emails (currently `rajm267749@gmail.com`)
   - `smtp.sender_email` / `smtp.app_password` → your Gmail + the 16-char App Password
   - `anthropic_api_key` → your Claude API key (or leave it and set the `ANTHROPIC_API_KEY` env var)
   - `claude_model` → `claude-opus-4-8` (smartest). Switch to `claude-haiku-4-5` or
     `claude-sonnet-4-6` for lower cost (see pricing).
   - `use_claude` → `true` to use Claude, `false` for plain RSS mode.

---

## Use

Preview both digests without sending (no email, prints to screen):
```
python news_agent.py --dry-run
```
Send the two emails for real:
```
python news_agent.py
```
or double-click **run.bat**.

---

## Cost (Claude)

One run reads ~28 short headlines and writes ~15 summaries — a tiny request.
Rough cost **per day** by model:

| Model (`claude_model`) | ~Cost/day | ~Cost/month |
|---|---|---|
| `claude-opus-4-8` (smartest) | ~$0.09 | ~$2.70 |
| `claude-sonnet-4-6` (balanced) | ~$0.05 | ~$1.50 |
| `claude-haiku-4-5` (cheapest) | ~$0.02 | ~$0.60 |

Change the model in `config.json` anytime.

---

## Run automatically at 7:30 AM (already set up)

A Windows Task Scheduler job named **"Daily AI News"** runs `run.bat` daily at 7:30 AM.
To change/remove it: open **Task Scheduler** → find "Daily AI News".

---

## Customize (`config.json`)

- `hours_lookback` — how far back to pull news (default 24)
- `max_items` — how many raw stories to hand Claude (default 28)
- `final_count` — how many AI-news stories Claude keeps for the newspaper (default 15;
  stock items are kept separately on top)
- `feeds` — add/remove any RSS/Atom source
