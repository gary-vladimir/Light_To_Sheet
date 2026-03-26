# YouTube Download Proxy Setup

YouTube blocks video downloads from cloud server IPs (GCP, AWS, etc.).
This guide sets up a tiny proxy on your Mac that downloads videos using
your residential IP and sends them to Cloud Run via a Cloudflare Tunnel.

```
User → Cloud Run (video2notes.app) → Cloudflare Tunnel → Your Mac → YouTube
                                      (proxy.video2notes.app)   (yt-dlp)
```

**Cost: $0** — Cloudflare Tunnel is free. Your Mac is already running.

---

## Prerequisites

- macOS with Python 3.10+
- `yt-dlp` and `flask` installed (`pip install yt-dlp flask`)
- `cloudflared` CLI (installed below)
- Deno installed (`brew install deno`) — required by yt-dlp for YouTube
- A domain on Cloudflare (we use `video2notes.app`)

---

## Step 1: Generate an API Key

Pick any random string as your shared secret. This prevents strangers from
using your proxy. Run this to generate one:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Save the output — you'll need it in steps 2 and 6. Example:
```
aB3dEf_GhIjKlMnOpQrStUvWxYz1234567890abc
```

---

## Step 2: Start the Download Proxy

From the project root:

```bash
cd ~/Documents/Light_To_Sheet
PROXY_API_KEY=your-secret-from-step-1 python3 download_proxy.py
```

You should see:
```
[proxy] Starting download proxy on port 8787
[proxy] API key is set (length=43)
```

**Test it** (in another terminal):
```bash
curl http://localhost:8787/health
# → {"status":"ok"}
```

---

## Step 3: Install Cloudflare Tunnel

```bash
brew install cloudflared
```

---

## Step 4: Authenticate cloudflared

```bash
cloudflared tunnel login
```

A browser window opens — select your domain (e.g., `video2notes.app`).
The terminal will print "You have successfully logged in" when done.

---

## Step 5: Create a Named Tunnel

```bash
cloudflared tunnel create piano-proxy
```

This prints a **Tunnel ID** (a UUID like `abcd1234-5678-...`). Note it — you
need it for the config file. It also creates a credentials JSON file at
`~/.cloudflared/<TUNNEL_ID>.json`.

---

## Step 6: Configure the Tunnel

Create the config file at `~/.cloudflared/config.yml`:

```yaml
tunnel: <TUNNEL_ID>
credentials-file: /Users/<YOUR_USERNAME>/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: proxy.video2notes.app
    service: http://localhost:8787
  - service: http_status:404
```

Replace `<TUNNEL_ID>` with the UUID from step 5, and `<YOUR_USERNAME>` with
your macOS username.

---

## Step 7: Add DNS Record

This creates a CNAME record pointing `proxy.video2notes.app` to your tunnel:

```bash
cloudflared tunnel route dns piano-proxy proxy.video2notes.app
```

---

## Step 8: Start the Tunnel

In a **new terminal** (keep the proxy running from step 2):

```bash
cloudflared tunnel run piano-proxy
```

---

## Step 9: Test It

```bash
curl https://proxy.video2notes.app/health
# → {"status":"ok"}
```

---

## Step 10: Configure Cloud Run

Set the proxy URL and API key as environment variables on your Cloud Run service:

```bash
gcloud run services update light-to-sheet \
  --region us-central1 \
  --set-env-vars "DOWNLOAD_PROXY_URL=https://proxy.video2notes.app,PROXY_API_KEY=your-secret-from-step-1"
```

**That's it!** The YouTube URL tab on your web app will now work.

---

## Step 11: End-to-End Test

1. Go to your app: [https://video2notes.app](https://video2notes.app)
2. Click the **YouTube URL** tab
3. Paste a Synthesia video URL
4. Click **Process Video**
5. Watch your Mac's terminal — you'll see `[proxy] Downloading: ...`

---

## Daily Usage

Every time you want the YouTube URL feature to work, open **two terminals**:

**Terminal 1 — Start the proxy:**
```bash
cd ~/Documents/Light_To_Sheet
PROXY_API_KEY=your-secret python3 download_proxy.py
```

**Terminal 2 — Start the tunnel:**
```bash
cloudflared tunnel run piano-proxy
```

That's it. The URL `proxy.video2notes.app` is permanent — no need to update
Cloud Run when you restart.

> **Tip:** The Upload Video tab always works, even when your Mac is off.
> The YouTube URL tab only works when both the proxy and tunnel are running.

---

## How the Piano Content Filter Works

The proxy includes a content filter that checks whether a YouTube video is
piano-related before downloading it. It examines the video's title,
description, tags, and channel name for piano-related keywords (piano,
Synthesia, keyboard, etc.).

If the video doesn't appear to be piano-related, the proxy returns a `403`
error. The web app displays this as a friendly amber/gold notice ("Not a
piano video") with a suggestion to try a Synthesia piano tutorial, rather
than a generic red error.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `[proxy] Failed: Deno is required` | Install Deno: `brew install deno` |
| `401 Unauthorized` from Cloud Run logs | API keys don't match — check both PROXY_API_KEY values |
| `Connection refused` in Cloud Run logs | Proxy or tunnel isn't running on your Mac |
| YouTube URL works but is slow | Video downloads at your home internet speed, then uploads to Cloud Run |
| Upload Video tab works, YouTube doesn't | Your Mac is offline or the tunnel isn't running |
| `cloudflared tunnel run` fails | Check that `~/.cloudflared/config.yml` has the correct tunnel ID and credentials path |
| DNS not resolving for proxy subdomain | Verify the CNAME was created: `dig proxy.video2notes.app CNAME +short` |
