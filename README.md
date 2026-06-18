# Daily AI/ML News Agent (AI-powered)

A Python agent that every morning:
1. **Gathers** worldwide AI/ML news from the last 24h (15 free RSS sources).
2. **Reads it with an LLM** (Cohere by default; Anthropic optional) — drops
   noise/duplicates, writes a clean one-line summary for each story, ranks by
   importance, groups by topic, and **separates stock-market items from real AI news**.
3. **Emails you TWO digests:**
   - 🗞️ **Daily AI Newspaper** — the AI/ML news
   - 📈 **Daily AI Stock & Market Watch** — AI stock/market items (separate email)

If the LLM is off/unavailable, it falls back to a single plain RSS email.

---

## What's required

| Requirement | Why | Cost |
|---|---|---|
| **Python 3** | Runs the agent | free |
| **feedparser + cohere** | Read feeds + call the LLM (`pip install -r requirements.txt`) | free |
| **Cohere API key** | So the LLM can edit/summarize/split the news | free trial tier |
| **Gmail App Password** | So the script can send the two emails | free |

---

## Setup (one time)

1. **Install dependencies**
   ```
   pip install -r requirements.txt
   ```

2. **Get a Cohere API key** — https://dashboard.cohere.com/api-keys (free trial key works).

3. **Get a Gmail App Password** (needed to send email — see detailed steps below).

4. **Create your config**
   - Copy `config.example.json` to `config.json`.
   - Fill in: `send_to`, `smtp.sender_email`, `smtp.app_password`, `cohere_api_key`.
   - `config.json` is git-ignored, so your keys stay private.

---

## How to get a Gmail App Password (step by step)

A Gmail App Password is a special 16-character password that lets a script send
mail from your account. (Your normal Gmail password will not work for SMTP.)

1. Go to your Google Account: **https://myaccount.google.com**
2. Open **Security** in the left menu.
3. Turn ON **2-Step Verification** (App Passwords only exist once this is on).
4. Now open **https://myaccount.google.com/apppasswords**
5. Type a name like `AI News Agent` and click **Create**.
6. Google shows a **16-character code** (like `abcd efgh ijkl mnop`).
7. Copy it, remove the spaces, and paste it into `config.json` →
   `smtp.app_password`. Also set `smtp.sender_email` to that same Gmail address.

> If `https://myaccount.google.com/apppasswords` says "not available", it's
> because 2-Step Verification isn't on yet — do step 3 first.

---

## Use

Preview both digests without sending:
```
python news_agent.py --dry-run
```
Send the two emails for real:
```
python news_agent.py
```
or double-click **run.bat**.

---

## Provider & model (config.json)

- `provider`: `"cohere"` (default) or `"anthropic"`.
- `cohere_model`: e.g. `command-r-08-2024` (default) or `command-a-03-2025` (smartest).
- `claude_model`: used only if `provider` is `"anthropic"` (e.g. `claude-opus-4-8`).
- `use_ai`: `true` to use the LLM, `false` for plain RSS mode.

---

## Run automatically at 7:30 AM (Windows)

A Task Scheduler job named **"Daily AI News"** runs `run.bat` daily at 7:30 AM.
Manage it in **Task Scheduler** under that name.

---

## Customize feeds & counts (config.json)

- `hours_lookback` — how far back to pull news (default 24)
- `max_items` — how many raw stories to hand the LLM (default 28)
- `final_count` — how many AI-news stories to keep (default 15; stock items kept separately)
- `feeds` — add/remove any RSS/Atom source
