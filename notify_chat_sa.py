#!/usr/bin/env python3
"""Send a message to a Google Chat space via the Chat API using a service account.

Messages are posted as the bot, so you receive notifications normally.
Works with personal Google accounts and Google Workspace. No browser auth needed.

Setup:
    1. pip install cryptography
    2. Place the service account JSON key as credentials.json next to this script
    3. Add the service account email to your Chat space as a member
    4. Set GOOGLE_CHAT_SPACE_ID in .env

Usage:
    ./notify_chat_sa.py "Deploy finished"
    ./notify_chat_sa.py --status success --title "Nightly Build" "Build #245 completed in 3m12s"
    tail -n 20 build.log | ./notify_chat_sa.py --status failure --title "Build Failed"

Required env:
    GOOGLE_CHAT_SPACE_ID   The space to post to, e.g. spaces/XXXXXXXXXXXXXXX
                           Find it in the Chat URL: chat.google.com/room/SPACE_ID/...
"""

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

STATUS_ICONS = {
    "success": "✅",
    "failure": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
}

CHAT_API = "https://chat.googleapis.com/v1"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/chat.bot"


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


def _b64(data):
    if isinstance(data, dict):
        data = json.dumps(data, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def get_access_token(creds_path):
    with open(creds_path, encoding="utf-8") as f:
        sa = json.load(f)

    if sa.get("type") != "service_account":
        raise ValueError("credentials.json is not a service account key file.")

    now = int(time.time())
    header = _b64({"alg": "RS256", "typ": "JWT"})
    payload = _b64({
        "iss": sa["client_email"],
        "scope": SCOPE,
        "aud": TOKEN_ENDPOINT,
        "iat": now,
        "exp": now + 3600,
    })
    signing_input = header + b"." + payload

    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError:
        print("Error: run 'pip install cryptography' first.", file=sys.stderr)
        sys.exit(1)

    private_key = serialization.load_pem_private_key(
        sa["private_key"].encode(), password=None
    )
    signature = private_key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    jwt = (signing_input + b"." + _b64(signature)).decode()

    data = urllib.parse.urlencode(
        {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": jwt,
        }
    ).encode()

    req = urllib.request.Request(TOKEN_ENDPOINT, data=data, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.load(resp)["access_token"]


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


def send(space_id, access_token, text, thread_key=None):
    url = f"{CHAT_API}/{space_id}/messages"
    if thread_key:
        url += "?messageReplyOption=REPLY_MESSAGE_FALLBACK_TO_NEW_THREAD"

    payload = {"text": text}
    if thread_key:
        payload["thread"] = {"threadKey": thread_key}

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json; charset=UTF-8",
            "Authorization": f"Bearer {access_token}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description="Send a Google Chat message via service account.")
    parser.add_argument("message", nargs="?", default=None, help="Message body. Reads stdin if omitted.")
    parser.add_argument("--title", default=None, help="Bold header line for the message.")
    parser.add_argument("--status", choices=sorted(STATUS_ICONS), default=None, help="Adds a status icon.")
    parser.add_argument("--thread-key", default=None, help="Group messages into a Chat thread.")
    parser.add_argument("--space-id", default=None, help="Override GOOGLE_CHAT_SPACE_ID for this call.")
    parser.add_argument("--quiet", action="store_true", help="Suppress success output.")
    args = parser.parse_args()

    find_and_load_dotenv()

    space_id = args.space_id or os.environ.get("GOOGLE_CHAT_SPACE_ID")
    if not space_id:
        print(
            "Error: GOOGLE_CHAT_SPACE_ID is not set.\n"
            "Set it in a .env file next to notify_chat_sa.py, or export it, or pass --space-id.\n"
            "Find it in the Chat URL: chat.google.com/room/SPACE_ID/...",
            file=sys.stderr,
        )
        return 1

    script_dir = os.path.dirname(os.path.abspath(__file__))
    creds_path = os.path.join(script_dir, "credentials.json")
    if not os.path.isfile(creds_path):
        print("Error: credentials.json not found next to notify_chat_sa.py.", file=sys.stderr)
        return 1

    message = args.message
    if message is None and not sys.stdin.isatty():
        message = sys.stdin.read().strip()

    text = build_text(args.title, args.status, message)
    if not text:
        print("Error: no message provided (arg, stdin, --title, or --status).", file=sys.stderr)
        return 1

    try:
        access_token = get_access_token(creds_path)
    except Exception as e:
        print(f"Error: could not get access token: {e}", file=sys.stderr)
        return 1

    try:
        status, body = send(space_id, access_token, text, args.thread_key)
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
