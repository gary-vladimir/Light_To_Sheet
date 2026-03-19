# YouTube Download Proxy Setup

YouTube blocks video downloads from cloud server IPs (GCP, AWS, etc.).
This guide sets up a tiny proxy on your Mac that downloads videos using
your residential IP and sends them to Cloud Run via a free Cloudflare Tunnel.

```
User → Cloud Run → Cloudflare Tunnel → Your Mac → YouTube
                                         (yt-dlp)
```

**Cost: $0** — Cloudflare Tunnel is free. Your Mac is already running.

---

## Prerequisites

- macOS with Python 3.10+
- `yt-dlp` and `flask` installed (`pip install yt-dlp flask`)
- `cloudflared` CLI (installed below)
- Deno installed (`brew install deno`) — required by yt-dlp for YouTube

---

## Step 1: Generate an API Key

Pick any random string as your shared secret. This prevents strangers from
using your proxy. Run this to generate one:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Save the output — you'll need it in steps 2 and 5. Example:
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

## Step 4: Start the Tunnel

In a **new terminal** (keep the proxy running):

```bash
cloudflared tunnel --url http://localhost:8787
```

Cloudflared will print something like:
```
Your quick Tunnel has been created! Visit it at:
  https://random-words-here.trycloudflare.com
```

**Copy that URL** — that's your proxy's public address.

> **Note:** The URL changes every time you restart `cloudflared`.
> For a permanent URL, set up a named tunnel (see "Optional: Permanent Tunnel" below).

---

## Step 5: Configure Cloud Run

Set the proxy URL and API key as environment variables on your Cloud Run service:

```bash
gcloud run services update light-to-sheet \
  --region us-central1 \
  --set-env-vars "DOWNLOAD_PROXY_URL=https://your-tunnel-url.trycloudflare.com,PROXY_API_KEY=your-secret-from-step-1"
```

**That's it!** The YouTube URL tab on your web app will now work.

---

## Step 6: Test It

1. Go to your app: https://light-to-sheet-2032166340.us-central1.run.app/
2. Click the **YouTube URL** tab
3. Paste a Synthesia video URL
4. Click **Process Video**
5. Watch your Mac's terminal — you'll see `[proxy] Downloading: ...`

---

## Daily Usage

Every time you want the YouTube URL feature to work:

1. **Start the proxy** (Terminal 1):
   ```bash
   cd ~/Documents/Light_To_Sheet
   PROXY_API_KEY=your-secret python3 download_proxy.py
   ```

2. **Start the tunnel** (Terminal 2):
   ```bash
   cloudflared tunnel --url http://localhost:8787
   ```

3. **Update Cloud Run** if the tunnel URL changed:
   ```bash
   gcloud run services update light-to-sheet \
     --region us-central1 \
     --update-env-vars "DOWNLOAD_PROXY_URL=https://new-tunnel-url.trycloudflare.com"
   ```

> **Tip:** The Upload Video tab always works, even when your Mac is off.
> The YouTube URL tab only works when both the proxy and tunnel are running.

---

## Optional: Permanent Tunnel URL (recommended)

Quick tunnels give you a random URL that changes on restart. For a stable URL:

### a) Create a Cloudflare account (free)
Go to https://dash.cloudflare.com and sign up.

### b) Authenticate cloudflared
```bash
cloudflared tunnel login
```

### c) Create a named tunnel
```bash
cloudflared tunnel create light-to-sheet-proxy
```

### d) Configure the tunnel
Create `~/.cloudflared/config.yml`:
```yaml
tunnel: light-to-sheet-proxy
credentials-file: /Users/YOUR_USERNAME/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: proxy.yourdomain.com
    service: http://localhost:8787
  - service: http_status:404
```

### e) Add DNS record
```bash
cloudflared tunnel route dns light-to-sheet-proxy proxy.yourdomain.com
```

### f) Run the tunnel
```bash
cloudflared tunnel run light-to-sheet-proxy
```

Now your proxy is always at `https://proxy.yourdomain.com` — no need to
update Cloud Run when you restart.

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `[proxy] Failed: Deno is required` | Install Deno: `brew install deno` |
| `401 Unauthorized` from Cloud Run logs | API keys don't match — check both PROXY_API_KEY values |
| `Connection refused` in Cloud Run logs | Proxy or tunnel isn't running on your Mac |
| YouTube URL works but is slow | Video downloads at your home internet speed, then uploads to Cloud Run |
| Upload Video tab works, YouTube doesn't | Your Mac is offline or the tunnel URL changed |
