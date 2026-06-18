"""
Daily AI/ML News Agent (AI-powered)
-----------------------------------
1. Pulls worldwide AI/ML news from the last 24h via RSS feeds.
2. An LLM editor (Cohere by default, Anthropic optional) drops noise/dupes,
   writes clean one-line summaries, ranks by importance, groups by topic,
   and SPLITS stock-market items away from real AI news.
3. Emails TWO digests to the address in config.json:
     - "Daily AI Newspaper"          (AI/ML news)
     - "Daily AI Stock & Market Watch" (AI stock/market items)
   If the editor is off/unavailable it falls back to a single raw-feed email.

Run:  python news_agent.py
Test (no email, prints both digests): python news_agent.py --dry-run
"""

import json
import os
import sys
import smtplib
import ssl
import re
import html
from email.mime.text import MIMEText
from email.utils import parsedate_to_datetime
from datetime import datetime, timezone, timedelta
from pathlib import Path

try:
    import feedparser
except ImportError:
    sys.exit("Missing dependency. Run:  pip install -r requirements.txt")

CONFIG_PATH = Path(__file__).with_name("config.json")

# Used when no config.json is present (e.g. running in Docker/Render via env vars).
DEFAULT_FEEDS = [
    "https://news.google.com/rss/search?q=artificial+intelligence+OR+machine+learning+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=%22AI+model%22+OR+%22LLM%22+OR+%22generative+AI%22+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=%22OpenAI%22+OR+%22Anthropic%22+OR+%22Google+DeepMind%22+OR+%22Mistral+AI%22+OR+%22xAI%22+OR+%22Perplexity%22+OR+%22Hugging+Face%22+OR+%22Nvidia%22+OR+%22Cohere%22+OR+%22Meta+AI%22+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=(%22AI+startup%22+OR+%22AI+company%22)+(funding+OR+raises+OR+valuation+OR+%22Series%22+OR+IPO)+when:2d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=fastest+growing+AI+startup+OR+%22AI+unicorn%22+when:3d&hl=en-US&gl=US&ceid=US:en",
    "https://techcrunch.com/category/artificial-intelligence/feed/",
    "https://venturebeat.com/category/ai/feed/",
    "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml",
    "https://www.technologyreview.com/topic/artificial-intelligence/feed",
    "https://the-decoder.com/feed/",
    "https://www.wired.com/feed/tag/ai/latest/rss",
    "https://huggingface.co/blog/feed.xml",
    "https://hnrss.org/newest?q=AI+OR+LLM+OR+%22machine+learning%22&points=100",
    "https://export.arxiv.org/rss/cs.AI",
    "https://export.arxiv.org/rss/cs.LG",
]


def _apply_env(config):
    """Overlay environment variables on top of config (env wins). Lets the agent
    run in Docker/Render with no config.json — everything comes from env vars."""
    g = os.environ.get
    if g("SEND_TO"):
        config["send_to"] = g("SEND_TO")
    smtp = config.setdefault("smtp", {})
    if g("SMTP_SENDER_EMAIL"):
        smtp["sender_email"] = g("SMTP_SENDER_EMAIL")
    if g("SMTP_APP_PASSWORD"):
        smtp["app_password"] = g("SMTP_APP_PASSWORD")
    if g("SMTP_HOST"):
        smtp["host"] = g("SMTP_HOST")
    if g("SMTP_PORT"):
        smtp["port"] = int(g("SMTP_PORT"))
    smtp.setdefault("host", "smtp.gmail.com")
    smtp.setdefault("port", 465)
    if g("MAILER"):
        config["mailer"] = g("MAILER")
    if g("RESEND_API_KEY"):
        config["resend_api_key"] = g("RESEND_API_KEY")
    if g("RESEND_FROM"):
        config["resend_from"] = g("RESEND_FROM")
    if g("PROVIDER"):
        config["provider"] = g("PROVIDER")
    if g("COHERE_API_KEY"):
        config["cohere_api_key"] = g("COHERE_API_KEY")
    if g("COHERE_MODEL"):
        config["cohere_model"] = g("COHERE_MODEL")
    if g("ANTHROPIC_API_KEY"):
        config["anthropic_api_key"] = g("ANTHROPIC_API_KEY")
    if g("CLAUDE_MODEL"):
        config["claude_model"] = g("CLAUDE_MODEL")
    if g("USE_AI"):
        config["use_ai"] = g("USE_AI").strip().lower() in ("1", "true", "yes", "on")
    config.setdefault("feeds", DEFAULT_FEEDS)
    return config


def load_config():
    config = {}
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
    config = _apply_env(config)
    if not config.get("send_to"):
        sys.exit("No recipient configured. Set 'send_to' in config.json or the SEND_TO env var.")
    return config


def clean(text):
    """Strip HTML tags and collapse whitespace from a summary."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", "", text)        # remove HTML tags
    text = html.unescape(text)                  # decode entities
    text = re.sub(r"\s+", " ", text).strip()
    return text


def one_line(text, limit=180):
    text = clean(text)
    if len(text) > limit:
        text = text[:limit].rsplit(" ", 1)[0] + "..."
    return text


def entry_time(entry):
    """Return a timezone-aware datetime for an entry, or None."""
    for key in ("published", "updated", "created"):
        val = entry.get(key)
        if val:
            try:
                dt = parsedate_to_datetime(val)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except Exception:
                pass
    # feedparser also exposes parsed structs
    for key in ("published_parsed", "updated_parsed"):
        st = entry.get(key)
        if st:
            try:
                return datetime(*st[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def source_name(entry, feed):
    # Google News tags the real publisher in entry.source.title
    src = entry.get("source")
    if isinstance(src, dict) and src.get("title"):
        return src["title"]
    title = feed.feed.get("title", "")
    return title or "Source"


def collect(config):
    cutoff = datetime.now(timezone.utc) - timedelta(hours=config.get("hours_lookback", 24))
    seen_titles = set()
    items = []

    for url in config["feeds"]:
        try:
            feed = feedparser.parse(url)
        except Exception as e:
            print(f"  ! Failed to read feed: {url} ({e})")
            continue

        for entry in feed.entries:
            title = clean(entry.get("title", ""))
            link = entry.get("link", "")
            if not title or not link:
                continue

            dt = entry_time(entry)
            if dt and dt < cutoff:
                continue  # too old

            key = title.lower()[:90]
            if key in seen_titles:
                continue
            seen_titles.add(key)

            items.append({
                "title": title,
                "link": link,
                "summary": one_line(entry.get("summary", "") or entry.get("description", "")),
                "source": source_name(entry, feed),
                "time": dt or datetime.now(timezone.utc),
            })

    # newest first, then cap
    items.sort(key=lambda x: x["time"], reverse=True)
    return items[: config.get("max_items", 15)]


STOCK_TOPIC = "Stocks & Markets"

TOPIC_ORDER = [
    "Models & Releases",
    "Funding & Business",
    "Research & Papers",
    "Tools & Products",
    "Policy & Industry",
    "Other",
]

EDITOR_INSTRUCTIONS = (
    "You are the editor of a daily AI newspaper. You are given a JSON list of raw "
    "news items collected from RSS feeds in the last 24 hours. Do the following:\n"
    "1. DROP only true noise: ads, pure opinion/listicles, and near-duplicates "
    "(keep the single best source for each story).\n"
    "2. CLASSIFY every kept item into exactly one topic:\n"
    "   - If it is primarily about STOCKS / share price / trading / market caps / "
    "'buy points' / 'price target' / investor analysis of AI companies, set topic to "
    "'" + STOCK_TOPIC + "'.\n"
    "   - Otherwise pick one of: " + ", ".join(TOPIC_ORDER) + ".\n"
    "3. KEEP the most important, genuinely useful items worldwide: model releases, "
    "research, funding, products, tools, policy, and the major + fast-growing AI companies "
    "(OpenAI, Anthropic, Google DeepMind, Mistral, xAI, Perplexity, Hugging Face, Nvidia, "
    "Meta AI, etc.).\n"
    "4. For each kept item write a clean, factual ONE-SENTENCE summary in your own words "
    "(no clickbait) and a clean headline. Return the item's 'id' exactly as given (an "
    "integer) — do NOT return URLs.\n"
    "5. Rank by importance, most important first. Return up to {n} non-stock stories PLUS "
    "all relevant '" + STOCK_TOPIC + "' items.\n"
    "Return only the structured result."
)


# JSON schema both providers use for the structured digest. The model returns the
# integer 'id' of each item it keeps (not the URL) — we map id -> real link locally.
DIGEST_SCHEMA = {
    "type": "object",
    "properties": {
        "stories": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "headline": {"type": "string"},
                    "summary": {"type": "string"},
                    "topic": {"type": "string"},
                },
                "required": ["id", "headline", "summary", "topic"],
            },
        }
    },
    "required": ["stories"],
}


def _payload(items):
    return [
        {"id": i, "title": it["title"], "summary": it["summary"], "source": it["source"]}
        for i, it in enumerate(items)
    ]


def _normalize(stories, items):
    """Map the model's [{id,headline,summary,topic}] back onto the real links."""
    out = []
    for s in stories:
        idx = s.get("id")
        if not isinstance(idx, int) or idx < 0 or idx >= len(items):
            continue
        title = s.get("headline") or items[idx]["title"]
        out.append({"title": title, "summary": s.get("summary", ""),
                    "link": items[idx]["link"], "source": "",
                    "topic": s.get("topic", "Other")})
    return out


def ai_edit(items, config):
    """Use an LLM (Cohere or Anthropic) to dedupe, denoise, summarize, rank, and
    categorize the items — splitting stock-market items into their own topic.

    Returns a list of item dicts, or None to fall back to raw feed mode.
    """
    provider = config.get("provider", "cohere").lower()
    if provider == "cohere":
        return _cohere_edit(items, config)
    if provider == "anthropic":
        return _anthropic_edit(items, config)
    print(f"  ! Unknown provider '{provider}'. Falling back to raw feed mode.")
    return None


def _cohere_edit(items, config):
    try:
        import cohere
    except ImportError:
        print("  ! 'cohere' not installed; falling back to raw feed mode.")
        return None

    api_key = config.get("cohere_api_key", "")
    if not api_key or "PASTE" in api_key:
        import os
        api_key = os.environ.get("COHERE_API_KEY", "")
    if not api_key:
        print("  ! No Cohere API key. Set 'cohere_api_key' in config.json or COHERE_API_KEY env. "
              "Falling back to raw feed mode.")
        return None

    n = config.get("final_count", 15)
    model = config.get("cohere_model", "command-r-08-2024")
    try:
        co = cohere.ClientV2(api_key=api_key, log_warning_experimental_features=False)
        resp = co.chat(
            model=model,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": EDITOR_INSTRUCTIONS.format(n=n)},
                {"role": "user",
                 "content": "Here are today's raw AI/ML news items as JSON:\n\n"
                            + json.dumps(_payload(items), ensure_ascii=False)},
            ],
            response_format={"type": "json_object", "schema": DIGEST_SCHEMA},
        )
        text = resp.message.content[0].text
        data = json.loads(text)
        return _normalize(data.get("stories", []), items)
    except Exception as e:
        print(f"  ! Cohere editing failed ({e}). Falling back to raw feed mode.")
        return None


def _anthropic_edit(items, config):
    try:
        import anthropic
    except ImportError:
        print("  ! 'anthropic' not installed; falling back to raw feed mode.")
        return None

    api_key = config.get("anthropic_api_key", "")
    if not api_key or "PASTE" in api_key:
        api_key = None  # SDK reads ANTHROPIC_API_KEY from the environment

    n = config.get("final_count", 15)
    model = config.get("claude_model", "claude-opus-4-8")
    try:
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        resp = client.messages.create(
            model=model,
            max_tokens=8000,
            system=EDITOR_INSTRUCTIONS.format(n=n),
            messages=[{
                "role": "user",
                "content": "Here are today's raw AI/ML news items as JSON:\n\n"
                           + json.dumps(_payload(items), ensure_ascii=False),
            }],
            output_config={"format": {"type": "json_schema", "schema": DIGEST_SCHEMA}},
        )
        text = next(b.text for b in resp.content if b.type == "text")
        data = json.loads(text)
        return _normalize(data.get("stories", []), items)
    except Exception as e:
        print(f"  ! Claude editing failed ({e}). Falling back to raw feed mode.")
        return None


def _story_html(it):
    summary = (f"<div style='color:#444;font-size:14px;margin:2px 0 0'>{html.escape(it['summary'])}</div>"
               if it.get("summary") else "")
    source = (f"<div style='color:#888;font-size:12px;margin:3px 0'>{html.escape(it['source'])}</div>"
              if it.get("source") else "")
    return f"""
        <div style="margin:0 0 18px;padding:0 0 14px;border-bottom:1px solid #eee">
          <a href="{html.escape(it['link'])}" style="font-size:16px;font-weight:600;color:#0b66c3;text-decoration:none">
            {html.escape(it['title'])}
          </a>
          {source}
          {summary}
        </div>"""


def build_html(items, title, accent="#0b66c3"):
    """Render a digest. If items carry a 'topic', group them in TOPIC_ORDER."""
    today = datetime.now().strftime("%A, %d %B %Y")
    grouped = any(it.get("topic") for it in items)

    if grouped:
        sections = []
        order = TOPIC_ORDER + [STOCK_TOPIC]
        seen_order = order + sorted({it.get("topic", "Other") for it in items} - set(order))
        for topic in seen_order:
            group = [it for it in items if it.get("topic") == topic]
            if not group:
                continue
            sections.append(f"<h2 style='font-size:15px;color:{accent};margin:22px 0 10px'>{html.escape(topic)}</h2>")
            sections.extend(_story_html(it) for it in group)
        body = "".join(sections)
    else:
        body = "".join(_story_html(it) for it in items)

    if not body:
        body = "<p>No fresh stories found in the lookback window.</p>"

    return f"""<!DOCTYPE html><html><body style="font-family:Arial,Helvetica,sans-serif;background:#f6f7f9;margin:0;padding:24px">
      <div style="max-width:640px;margin:0 auto;background:#fff;border-radius:10px;padding:28px">
        <h1 style="font-size:22px;margin:0 0 4px">{title}</h1>
        <div style="color:#888;font-size:13px;margin:0 0 20px">{today} · {len(items)} stories · worldwide</div>
        {body}
        <div style="color:#aaa;font-size:11px;margin-top:18px">Auto-generated by your AI News Agent.</div>
      </div>
    </body></html>"""


def build_text(items, title):
    today = datetime.now().strftime("%A, %d %B %Y")
    lines = [f"{title} - {today}", f"{len(items)} stories", ""]
    for i, it in enumerate(items, 1):
        tag = f" [{it['topic']}]" if it.get("topic") else (f"  [{it['source']}]" if it.get("source") else "")
        lines.append(f"{i}. {it['title']}{tag}")
        if it.get("summary"):
            lines.append(f"   {it['summary']}")
        lines.append(f"   {it['link']}")
        lines.append("")
    return "\n".join(lines)


def _send_via_resend(config, subject, html_body):
    """Send over HTTPS using the Resend API — works on hosts (like Render) that
    block outbound SMTP ports."""
    import urllib.request
    import urllib.error
    key = config.get("resend_api_key") or os.environ.get("RESEND_API_KEY", "")
    if not key or "PASTE" in key:
        sys.exit("RESEND_API_KEY not set. Get one at https://resend.com and set RESEND_API_KEY "
                 "(env) or resend_api_key (config.json).")
    sender = config.get("resend_from") or "AI News Agent <onboarding@resend.dev>"
    payload = json.dumps({
        "from": sender,
        "to": [config["send_to"]],
        "subject": subject,
        "html": html_body,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.resend.com/emails", data=payload, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
    except urllib.error.HTTPError as e:
        sys.exit(f"Resend API error {e.code}: {e.read().decode('utf-8', 'replace')}")


def _send_via_smtp(config, subject, html_body):
    smtp = config["smtp"]
    if "PASTE" in smtp.get("app_password", "") or "YOUR_" in smtp.get("sender_email", ""):
        sys.exit("\nSMTP not configured. Edit config.json -> smtp.sender_email and smtp.app_password "
                 "(create a Gmail App Password at https://myaccount.google.com/apppasswords).")
    msg = MIMEText(html_body, "html", "utf-8")
    msg["Subject"] = subject
    msg["From"] = smtp["sender_email"]
    msg["To"] = config["send_to"]
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(smtp["host"], smtp["port"], context=context) as server:
        server.login(smtp["sender_email"], smtp["app_password"])
        server.send_message(msg)


def send_email(config, items, subject, title, accent="#0b66c3"):
    html_body = build_html(items, title, accent)
    mailer = config.get("mailer", "smtp").lower()
    if mailer == "resend":
        _send_via_resend(config, subject, html_body)
    else:
        _send_via_smtp(config, subject, html_body)
    print(f"✅ Sent '{subject}' ({len(items)} stories) via {mailer} to {config['send_to']}")


def split_news_and_stocks(stories):
    """Return (news_items, stock_items) based on the topic Claude assigned."""
    news = [s for s in stories if s.get("topic") != STOCK_TOPIC]
    stocks = [s for s in stories if s.get("topic") == STOCK_TOPIC]
    return news, stocks


def main():
    dry_run = "--dry-run" in sys.argv
    config = load_config()
    today = datetime.now().strftime("%d %b %Y")
    print("Gathering worldwide AI/ML news from the last "
          f"{config.get('hours_lookback', 24)}h ...")
    items = collect(config)
    print(f"Found {len(items)} fresh stories.")
    if not items:
        print("Nothing found. Skipping.")
        return

    # AI editor dedupes, summarizes, ranks, and splits news vs stock-market items.
    news, stocks = items, []
    if config.get("use_ai", config.get("use_claude", True)):
        provider = config.get("provider", "cohere")
        model = config.get("cohere_model" if provider == "cohere" else "claude_model", "")
        print(f"Asking the AI editor ({provider} {model}) to edit, summarize, "
              "and split AI news vs stock-market items ...")
        edited = ai_edit(items, config)
        if edited is not None:
            news, stocks = split_news_and_stocks(edited)
            print(f"Editor kept {len(news)} AI-news + {len(stocks)} stock-market stories.")

    if dry_run:
        print("\n--- DRY RUN (no email sent) ---\n")
        print(build_text(news, "🗞️ Daily AI Newspaper"))
        print("\n" + "=" * 50 + "\n")
        print(build_text(stocks, "📈 Daily AI Stock & Market Watch"))
        return

    # Email 1: AI/ML news
    if news:
        send_email(config, news, f"🗞️ Daily AI Newspaper - {today}",
                   "🗞️ Daily AI Newspaper")
    # Email 2: AI stock-market watch (separate email)
    if stocks:
        send_email(config, stocks, f"📈 Daily AI Stock & Market Watch - {today}",
                   "📈 Daily AI Stock &amp; Market Watch", accent="#0a8a4a")
    if not news and not stocks:
        print("Nothing to send.")


if __name__ == "__main__":
    main()
