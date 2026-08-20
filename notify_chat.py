#!/usr/bin/env python3
"""Send a message to a Google Chat space via an Incoming Webhook.

Usage:
    ./notify_chat.py "Deploy finished"
    ./notify_chat.py --status success --title "Nightly Build" "Build #245 completed in 3m12s"
    tail -n 20 build.log | ./notify_chat.py --status failure --title "Build Failed"

Configuration comes from environment variables, loaded from a .env file
(next to this script, or in the current directory) if present. CI-provided
environment variables always take precedence over .env values.

Required:
    GOOGLE_CHAT_WEBHOOK_URL   The Incoming Webhook URL for the target space.
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

STATUS_ICONS = {
    "success": "✅",
    "failure": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
}


def load_dotenv(path):
    if not os.path.isfile(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            os.environ.setdefault(key, value)


def find_and_load_dotenv():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(script_dir, ".env"))
    cwd_env = os.path.join(os.getcwd(), ".env")
    if os.path.abspath(cwd_env) != os.path.join(script_dir, ".env"):
        load_dotenv(cwd_env)


def build_text(title, status, message):
    parts = []
    icon = STATUS_ICONS.get(status, "")
    if title:
        header = f"{icon} *{title}*".strip() if icon else f"*{title}*"
        parts.append(header)
    elif icon:
        parts.append(icon)
    if message:
        parts.append(message)
    return "\n".join(parts)


def send(webhook_url, text, thread_key=None):
    url = webhook_url
    if thread_key:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}threadKey={urllib.parse.quote(thread_key)}"

    payload = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json; charset=UTF-8"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description="Send a Google Chat message via Incoming Webhook.")
    parser.add_argument("message", nargs="?", default=None, help="Message body. Reads stdin if omitted.")
    parser.add_argument("--title", default=None, help="Bold header line for the message.")
    parser.add_argument("--status", choices=sorted(STATUS_ICONS), default=None, help="Adds a status icon.")
    parser.add_argument("--thread-key", default=None, help="Group messages into a Chat thread.")
    parser.add_argument("--webhook-url", default=None, help="Override GOOGLE_CHAT_WEBHOOK_URL.")
    parser.add_argument("--quiet", action="store_true", help="Suppress success output.")
    args = parser.parse_args()

    find_and_load_dotenv()

    webhook_url = args.webhook_url or os.environ.get("GOOGLE_CHAT_WEBHOOK_URL")
    if not webhook_url:
        print(
            "Error: GOOGLE_CHAT_WEBHOOK_URL is not set.\n"
            "Set it in a .env file next to notify_chat.py, or export it, or pass --webhook-url.",
            file=sys.stderr,
        )
        return 1

    message = args.message
    if message is None and not sys.stdin.isatty():
        message = sys.stdin.read().strip()

    text = build_text(args.title, args.status, message)
    if not text:
        print("Error: no message provided (arg, stdin, --title, or --status).", file=sys.stderr)
        return 1

    try:
        status, body = send(webhook_url, text, args.thread_key)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(f"Error: Google Chat rejected the message (HTTP {e.code}): {body}", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"Error: could not reach Google Chat: {e.reason}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Sent (HTTP {status}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
