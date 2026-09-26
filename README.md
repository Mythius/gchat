# gchat

A tiny, dependency-free CLI that posts a message to a Google Chat space via the
Chat REST API with OAuth 2.0. Works with personal Google accounts and Google
Workspace — no webhook or organization account required.

## How it works

`notify_chat.py` calls the Google Chat API with a short-lived access token,
refreshing it automatically from a stored refresh token. `setup_oauth.py` does
the one-time browser-based consent flow to create that token file.

## Setup

### 1. Enable the Google Chat API and create OAuth credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/) and create or
   select a project.
2. **APIs & Services → Enable APIs** → search for "Google Chat API" → Enable.
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**.
   - Application type: **Desktop app**.
   - Name it anything (e.g. "gchat notifier").
4. Download the generated `credentials.json` and place it next to this script.

> If prompted to configure the OAuth consent screen, set it to **Internal** (if
> Workspace) or **External** with yourself as a test user. You only need the
> `chat.messages.create` scope.

### 2. Clone the repo and authorize it

```bash
git clone <this-repo-url> /opt/gchat-notify
cd /opt/gchat-notify
cp .env.example .env
chmod +x notify_chat.py setup_oauth.py
python3 setup_oauth.py
```

A browser window will open for Google sign-in and consent. After you approve,
`token.json` is saved next to the script — keep it private (it's git-ignored).

### 3. Configure your space ID

Find your space ID in the Google Chat URL when you're viewing the space:

```
https://chat.google.com/room/XXXXXXXXXXXXXXXXX/...
                             ↑ this is your SPACE_ID
```

Edit `.env`:

```
GOOGLE_CHAT_SPACE_ID=spaces/XXXXXXXXXXXXXXXXX
```

### 4. Test it

```bash
./notify_chat.py "Hello from the CI server"
```

### 5. Call it from your CI pipelines

```bash
if ./deploy.sh; then
    /opt/gchat-notify/notify_chat.py --status success --title "Deploy" "Deploy of $APP_NAME finished."
else
    /opt/gchat-notify/notify_chat.py --status failure --title "Deploy" "Deploy of $APP_NAME failed. Check logs."
fi
```

Pipe log output as the message body:

```bash
tail -n 20 build.log | ./notify_chat.py --status failure --title "Build Failed"
```

## CLI reference

```
notify_chat.py [message] [options]

  message            Message text. If omitted, read from stdin.
  --title TEXT        Bold header line shown above the message.
  --status {failure,info,success,warning}
                      Prepends a ✅ / ❌ / ⚠️ / ℹ️ icon.
  --thread-key KEY    Groups messages into a single Chat thread.
  --space-id ID       Override GOOGLE_CHAT_SPACE_ID for this call.
  --quiet             Suppress the "Sent" confirmation on success.
```

Exit code is `0` on success and `1` on any failure — safe to check in pipelines.

## Token management

`token.json` stores your refresh token and is updated automatically when the
access token expires (every hour). You should not need to re-run `setup_oauth.py`
unless you revoke the app's access at
[myaccount.google.com/permissions](https://myaccount.google.com/permissions).

## Multiple spaces

Pass `--space-id` per call, or set `GOOGLE_CHAT_SPACE_ID` in the environment
before running (overrides `.env`).

## Files

| File | Purpose |
|---|---|
| `notify_chat.py` | Main CLI — send messages |
| `setup_oauth.py` | One-time OAuth setup — creates `token.json` |
| `credentials.json` | OAuth client secrets from Google Cloud Console (git-ignored) |
| `token.json` | Saved tokens, auto-refreshed (git-ignored) |
| `.env` | Your space ID config (git-ignored) |
