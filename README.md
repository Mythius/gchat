# gchat

A tiny, dependency-free CLI that posts a message to a Google Chat space via an
Incoming Webhook. Built so any CI pipeline can drop a one-line call at the end
of a job and have it show up in Chat.

## How it works

Google Chat spaces support "Incoming Webhooks" — a secret URL you POST JSON
to, no OAuth or service account required. `notify_chat.py` reads that URL
from a `.env` file and sends your message to it.

## Setup (on your Linux server)

### 1. Create a Google Chat space and webhook

1. In Google Chat, create (or pick) a space you want CI notifications to land
   in — e.g. a space called "CI Alerts". Turn on notifications for it so it
   pings you like a DM would.
2. Click the space name at the top > **Apps & integrations** > **Add webhook**.
3. Name it (e.g. "CI Notifier"), click **Save**, then copy the generated
   webhook URL.

### 2. Clone this repo and configure it

```bash
git clone <this-repo-url> /opt/gchat-notify   # or wherever you keep it
cd /opt/gchat-notify
cp .env.example .env
chmod +x notify_chat.py
```

Edit `.env` and paste your webhook URL:

```
GOOGLE_CHAT_WEBHOOK_URL=https://chat.googleapis.com/v1/spaces/AAA.../messages?key=...&token=...
```

`.env` is git-ignored, so it stays local to the server.

### 3. Check Python is available

```bash
python3 --version
```

Any Python 3.6+ works — the script uses only the standard library, so
there's nothing to `pip install`.

### 4. Test it

```bash
./notify_chat.py "Hello from the CI server"
```

You should see the message appear in the Chat space within a couple seconds.

### 5. Call it from your CI pipelines

At the end of a pipeline's bash script:

```bash
if ./deploy.sh; then
    /opt/gchat-notify/notify_chat.py --status success --title "Deploy" "Deploy of $APP_NAME finished."
else
    /opt/gchat-notify/notify_chat.py --status failure --title "Deploy" "Deploy of $APP_NAME failed. Check logs."
fi
```

You can also pipe log output in as the message body:

```bash
tail -n 20 build.log | ./notify_chat.py --status failure --title "Build Failed"
```

## CLI reference

```
notify_chat.py [message] [options]

  message            Message text. If omitted, read from stdin.
  --title TEXT        Bold header line shown above the message.
  --status {success,failure,warning,info}
                      Prepends a ✅ / ❌ / ⚠️ / ℹ️ icon.
  --thread-key KEY    Groups messages into a single Chat thread.
  --webhook-url URL   Override GOOGLE_CHAT_WEBHOOK_URL for this call.
  --quiet             Suppress the "Sent" confirmation on success.
```

Exit code is `0` on success and `1` on any failure (missing config, network
error, or Chat API rejection) — safe to check in a pipeline if you want to
react to notification failures specifically.

## Multiple pipelines, multiple spaces

If different pipelines should post to different spaces, either:

- Export `GOOGLE_CHAT_WEBHOOK_URL` in that pipeline's own environment (it
  takes precedence over `.env`), or
- Pass `--webhook-url` explicitly per call.
