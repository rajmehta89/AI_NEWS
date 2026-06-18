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

## Deploy to the cloud with Docker + Render (runs even when your PC is off)

This repo includes a `Dockerfile` and `render.yaml` so you can run it as a
**Render Cron Job**. No `config.json` is needed in the cloud — all settings come
from environment variables.

1. Push this repo to GitHub (already done: `rajmehta89/AI_NEWS`).
2. On https://render.com → **New + → Blueprint** → connect this repo.
   Render reads `render.yaml` and creates a Cron Job.
3. In the service's **Environment** tab, set these secrets:
   - `RESEND_API_KEY` — your Resend key (see below — Render blocks SMTP, so cloud uses Resend)
   - `SEND_TO` — who receives the emails
   - `COHERE_API_KEY` — your Cohere key
   (`MAILER=resend`, `RESEND_FROM`, `PROVIDER`, `COHERE_MODEL`, `USE_AI` are pre-filled in `render.yaml`.)
4. Schedule is in `render.yaml` (`30 1 * * *` = 01:30 UTC = 7:00 AM IST). Edit to taste.
5. Use **"Trigger Run"** in Render to test it immediately.

> ⚠️ **Important: Render blocks outbound SMTP (ports 25/465/587).** Gmail SMTP will
> fail with `Network is unreachable`. That's why cloud runs use **Resend** (HTTPS).
> Also make sure the service is a **Cron Job**, not a Web Service (the Blueprint sets
> this) — a Web Service fails with "No open ports detected".

**Get a Resend API key (free):**
1. Sign up at **https://resend.com** (use your Gmail so you can email yourself without a domain).
2. **API Keys** → **Create API Key** → copy it (`re_...`).
3. Set it as `RESEND_API_KEY` in Render.
4. Default sender is `onboarding@resend.dev` (Resend's test sender). To send to *any*
   address or use your own from-address, verify a domain in Resend and set `RESEND_FROM`.

**Run the Docker image locally instead:**
```
docker build -t ai-news-agent .
docker run --rm \
  -e SEND_TO=you@gmail.com \
  -e SMTP_SENDER_EMAIL=you@gmail.com \
  -e SMTP_APP_PASSWORD=your16charapppw \
  -e COHERE_API_KEY=your_cohere_key \
  ai-news-agent
```

### Environment variables (cloud / Docker)

| Var | Meaning |
|---|---|
| `SEND_TO` | recipient email |
| `MAILER` | `smtp` (local default) or `resend` (cloud/Render) |
| `RESEND_API_KEY` | Resend key — required when `MAILER=resend` |
| `RESEND_FROM` | sender, default `AI News Agent <onboarding@resend.dev>` |
| `SMTP_SENDER_EMAIL` | Gmail you send from (SMTP/local only) |
| `SMTP_APP_PASSWORD` | Gmail App Password (SMTP/local only) |
| `SMTP_HOST` / `SMTP_PORT` | default `smtp.gmail.com` / `465` |
| `PROVIDER` | `cohere` (default) or `anthropic` |
| `COHERE_API_KEY` / `COHERE_MODEL` | Cohere key + model |
| `ANTHROPIC_API_KEY` / `CLAUDE_MODEL` | only if `PROVIDER=anthropic` |
| `USE_AI` | `true` to use the LLM, `false` for raw RSS |

---

## Run automatically at 7:30 AM (Windows, local)

A Task Scheduler job named **"Daily AI News"** runs `run.bat` daily at 7:30 AM.
Manage it in **Task Scheduler** under that name.

---

## Customize feeds & counts (config.json)

- `hours_lookback` — how far back to pull news (default 24)
- `max_items` — how many raw stories to hand the LLM (default 28)
- `final_count` — how many AI-news stories to keep (default 15; stock items kept separately)
- `feeds` — add/remove any RSS/Atom source
