# Deployment Guide: Light to Sheet

This guide walks you through deploying Light to Sheet as a public web app with Google Sign-In authentication. By the end, you'll have a live URL anyone can visit.

**What you'll set up:**

- Firebase Authentication (Google Sign-In) - handles user login
- Google Cloud Run - hosts your app, scales automatically
- Total monthly cost: **$0** (free tier)

**Time required:** ~30 minutes

---

## Prerequisites

- A Google account (Gmail)
- A credit card for Google Cloud verification (you will NOT be charged — it's only for identity verification, and we stay within the free tier)
- Git installed on your machine
- Your code pushed to a GitHub repository (recommended but not required)

---

## Step 1: Create a Google Cloud Account

If you already have a Google Cloud account, skip to Step 2.

1. Go to [https://cloud.google.com](https://cloud.google.com)
2. Click **Get started for free**
3. Sign in with your Google account
4. Enter your billing information (credit card required for verification)
5. You'll receive **$300 in free credits** valid for 90 days
6. After the free trial, the always-free tier kicks in — Cloud Run's free tier is very generous

> **Will I be charged?** No. Google Cloud does not auto-charge when the free trial ends. You must manually upgrade to a paid account. Even then, our setup stays well within the always-free tier limits.

---

## Step 2: Create a Google Cloud Project

1. Go to [https://console.cloud.google.com](https://console.cloud.google.com)
2. Click the project dropdown at the top of the page (it might say "Select a project" or show an existing project name)
3. Click **New Project**
4. Enter a project name: `light-to-sheet`
5. Click **Create**
6. Wait a few seconds, then make sure the new project is selected in the dropdown

**Write down your Project ID** — you'll see it below the project name (it looks like `light-to-sheet` or `light-to-sheet-12345`). You'll need this later.

---

## Step 3: Set Up Firebase Authentication

### 3a. Create a Firebase Project

1. Go to [https://console.firebase.google.com](https://console.firebase.google.com)
2. Click **Create a project** (or **Add project**)
3. Enter project name: `light-to-sheet`
4. Firebase will detect your existing Google Cloud project — **select it** to link them together
5. You can disable Google Analytics (not needed) — click **Continue**
6. Click **Create project**, then **Continue** when it's ready

### 3b. Enable Google Sign-In

1. In the Firebase Console, click **Authentication** in the left sidebar (under "Build")
2. Click **Get started**
3. Click the **Sign-in method** tab
4. Click **Google** in the providers list
5. Toggle the **Enable** switch to ON
6. Enter a **Project support email** (your Gmail address)
7. Click **Save**

### 3c. Register Your Web App

1. In the Firebase Console, click the **gear icon** (top-left, next to "Project Overview") then **Project settings**
2. Scroll down to **Your apps** section
3. Click the **web icon** (`</>`) to add a web app
4. Enter a nickname: `light-to-sheet-web`
5. Do NOT check "Also set up Firebase Hosting"
6. Click **Register app**
7. You'll see a code block with `firebaseConfig`. It looks like this:

```javascript
const firebaseConfig = {
  apiKey: "AIzaSyB1234567890abcdefg",
  authDomain: "light-to-sheet.firebaseapp.com",
  projectId: "light-to-sheet",
  storageBucket: "light-to-sheet.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:abcdef123456"
};
```

1. **Copy these values.** You need them for the next step.
2. Click **Continue to console**

> **Are these values secret?** No. Firebase config values are designed to be public. They only identify your project. Security is enforced server-side by verifying tokens.

### 3d. Paste Config Into Your Code

Open `templates/index.html` and find this block near the top (around line 17):

```javascript
const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_PROJECT.firebaseapp.com",
  projectId: "YOUR_PROJECT_ID",
  appId: "YOUR_APP_ID",
};
```

Replace the placeholder values with the real values from Step 3c. For example:

```javascript
const firebaseConfig = {
  apiKey: "AIzaSyB1234567890abcdefg",
  authDomain: "light-to-sheet.firebaseapp.com",
  projectId: "light-to-sheet",
  appId: "1:123456789:web:abcdef123456",
};
```

Save the file.

---

## Step 4: Install the Google Cloud CLI

### macOS (using Homebrew)

```bash
brew install --cask google-cloud-sdk
```

### macOS (manual install)

```bash
curl https://sdk.cloud.google.com | bash
```

Then restart your terminal.

### Windows

Download the installer from: [https://cloud.google.com/sdk/docs/install](https://cloud.google.com/sdk/docs/install)

### Verify Installation

```bash
gcloud --version
```

You should see version info. If you get "command not found", restart your terminal.

---

## Step 5: Authenticate and Configure gcloud

Run these commands one at a time:

```bash
# Log in to Google Cloud (opens a browser window)
gcloud auth login

# Set your project (replace with YOUR project ID from Step 2)
gcloud config set project light-to-sheet
```

When `gcloud auth login` runs, it will open your browser. Sign in with the same Google account you used for Cloud Console.

---

## Step 6: Enable Required APIs

These APIs need to be turned on before deploying. Run both commands:

```bash
# Cloud Run API (hosts your app)
gcloud services enable run.googleapis.com

# Artifact Registry API (stores your Docker image)
gcloud services enable artifactregistry.googleapis.com

# Cloud Build API (builds your Docker image)
gcloud services enable cloudbuild.googleapis.com
```

Each command takes about 10-30 seconds. You'll see "Operation finished successfully" for each.

---

## Step 7: Deploy to Cloud Run

Make sure you are in the project root directory (where `Dockerfile` is located):

```bash
cd /path/to/Light_To_Sheet
```

Grant Storage access

```bash
gcloud projects add-iam-policy-binding light-to-sheet \
  --member='serviceAccount:2032166340-compute@developer.gserviceaccount.com' \
  --role='roles/storage.admin'
```

Grant Cloud Build access

```bash
gcloud projects add-iam-policy-binding light-to-sheet \
  --member='serviceAccount:2032166340-compute@developer.gserviceaccount.com' \
  --role='roles/cloudbuild.builds.builder'
```

Then deploy:

```bash
gcloud run deploy light-to-sheet \
  --source . \
  --region us-central1 \
  --max-instances 1 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --allow-unauthenticated
```

**What each flag does:**

| Flag | Purpose |
|------|---------|
| `--source .` | Builds the Docker image from your Dockerfile |
| `--region us-central1` | Deploys to Iowa, USA (good free tier coverage) |
| `--max-instances 1` | Keeps all requests on one server (so file downloads work) |
| `--memory 2Gi` | 2 GB RAM for video processing |
| `--cpu 2` | 2 CPU cores for FFmpeg |
| `--timeout 900` | Allows up to 15 minutes per request (long videos need this) |
| `--allow-unauthenticated` | Lets anyone visit the page (Firebase handles login, not Cloud Run) |

**During deployment:**

- If asked to create an Artifact Registry repository, type **Y** and press Enter
- If asked to enable APIs, type **Y** and press Enter
- The first deployment takes 5-10 minutes (building the Docker image)

**When it finishes**, you'll see output like:

```
Service [light-to-sheet] revision [light-to-sheet-00001-abc] has been deployed
and is serving 100 percent of traffic.

Service URL: https://light-to-sheet-abc123-uc.a.run.app
```

**Copy that Service URL** — this is your live public URL!

---

## Step 8: Add Your URL to Firebase Authorized Domains

Firebase needs to know your Cloud Run URL is legitimate, otherwise the Google Sign-In popup will refuse to work.

1. Go to [Firebase Console](https://console.firebase.google.com) and select your project
2. Click **Authentication** in the left sidebar
3. Click the **Settings** tab
4. Click **Authorized domains**
5. Click **Add domain**
6. Paste your Cloud Run URL **without the `https://`**. For example:

   ```
   light-to-sheet-abc123-uc.a.run.app
   ```

7. Click **Add**

---

## Step 9: Test Your Deployment

1. Open your Service URL in a browser (the URL from Step 7)
2. You should see the Light to Sheet app with "Sign in to Process" button
3. Paste a YouTube URL of a Synthesia piano video
4. Click "Sign in to Process"
5. A Google Sign-In popup should appear
6. Sign in with your Google account
7. The video should start processing automatically
8. After processing, you should see the sheet music, frame preview, and download buttons

If everything works, congratulations — your app is live!

---

## Step 10: YouTube Cookies Setup (Required for Cloud Run)

YouTube blocks video downloads from cloud server IPs (it thinks the server is a bot). To fix this, you provide a cookies file from a real browser session so yt-dlp can authenticate as you.

### 10a. Export Your YouTube Cookies

You need a browser extension that exports cookies in **Netscape format** (the standard `cookies.txt` format).

**Recommended extension:** "Get cookies.txt LOCALLY" (available for Chrome and Firefox).

1. Install the extension: [Chrome Web Store](https://chromewebstore.google.com/detail/get-cookiestxt-locally/cclelndahbckbenkjhflpdbgdldlbecc)
2. Go to [https://www.youtube.com](https://www.youtube.com) and **make sure you are signed in** to your Google account
3. Click the extension icon in your browser toolbar
4. Click **Export** (or "Export as cookies.txt")
5. Save the file as `cookies.txt`

> **Important:** You must be signed into YouTube in the browser when exporting. The cookies prove to YouTube that a real human authorized the download.

### 10b. Upload Cookies as a Cloud Run Secret

Google Cloud Secret Manager stores your cookies securely and mounts them into the container as a file.

```bash
# Enable the Secret Manager API
gcloud services enable secretmanager.googleapis.com

# Create the secret from your cookies file
gcloud secrets create youtube-cookies \
  --data-file=cookies.txt

# Grant the Cloud Run service account access to the secret
gcloud secrets add-iam-policy-binding youtube-cookies \
  --member="serviceAccount:$(gcloud iam service-accounts list --format='value(email)' --filter='displayName:Compute Engine default')" \
  --role="roles/secretmanager.secretAccessor"
```

### 10c. Redeploy with the Secret Mounted

Now redeploy the app with the secret mounted as a file inside the container:

```bash
gcloud run deploy light-to-sheet \
  --source . \
  --region us-central1 \
  --max-instances 1 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --allow-unauthenticated \
  --update-secrets=/secrets/youtube_cookies/cookies.txt=youtube-cookies:latest
```

The key addition is `--update-secrets` which mounts the secret at `/secrets/youtube_cookies/cookies.txt` inside the container. The app automatically detects this file and passes it to yt-dlp.

### 10d. Refreshing Cookies (When They Expire)

YouTube cookies typically last **several months**, but they will eventually expire. When downloads start failing again with bot-detection errors:

1. Re-export cookies from your browser (repeat Step 10a)
2. Update the secret:

   ```bash
   gcloud secrets versions add youtube-cookies \
     --data-file=cookies.txt
   ```

3. Redeploy the app (repeat Step 10c) — Cloud Run needs a new revision to pick up the updated secret

> **Tip:** You'll know cookies expired when you see "Sign in to confirm you're not a bot" in the Cloud Run logs.

---

## Troubleshooting

### "Sign in to confirm you're not a bot" / YouTube download fails

- You need to set up YouTube cookies — see Step 10 above
- If cookies were already set up, they may have expired — refresh them (Step 10d)
- Check that you were signed into YouTube when you exported the cookies

### "Sign-in popup doesn't appear" or "auth/unauthorized-domain" error

- Make sure you added your Cloud Run URL to Firebase Authorized Domains (Step 8)
- Make sure the URL doesn't include `https://` when adding it

### "Processing failed" error

- Check Cloud Run logs: `gcloud run services logs read light-to-sheet --region us-central1`
- The video might be too long, or the YouTube URL might be invalid

### Deployment fails with "build error"

- Make sure your `Dockerfile` is in the project root directory (not inside `.devcontainer/`)
- Make sure all files are saved and committed

### "Authentication required" 401 error

- The Firebase config in `index.html` might be wrong — double-check the values from Step 3c
- Clear your browser cache and try again

### App is slow to load (10-30 seconds)

- This is a **cold start** — the container needs to boot up when it hasn't been used recently
- Subsequent requests within 15 minutes will be fast
- This is normal for the free tier (the server scales to zero when idle to save cost)

---

## How to Redeploy After Code Changes

Whenever you make changes to your code and want to update the live app:

```bash
cd /path/to/Light_To_Sheet
gcloud run deploy light-to-sheet \
  --source . \
  --region us-central1 \
  --max-instances 1 \
  --memory 2Gi \
  --cpu 2 \
  --timeout 900 \
  --allow-unauthenticated \
  --update-secrets=/secrets/youtube_cookies/cookies.txt=youtube-cookies:latest
```

It's the same command as the first deploy (with the cookies secret). Subsequent deploys are faster (3-5 minutes) because Docker layer caching kicks in.

---

## Cost Breakdown

| Service | Free Tier | Your Expected Usage | Monthly Cost |
|---------|-----------|-------------------|--------------|
| Firebase Auth | Unlimited users | Any | **$0** |
| Cloud Run | 180,000 vCPU-seconds/month | ~750 video requests (2 min each) | **$0** |
| Cloud Build | 120 build-minutes/day | A few deploys | **$0** |
| Artifact Registry | 500 MB storage | 1 Docker image (~1 GB, but within free tier) | **$0** |
| **Total** | | | **$0/month** |

Plus your **$300 free credit** covers the first 90 days regardless.

---

## Scaling Up Later (If Your App Gets Popular)

When you start getting more traffic and need to handle multiple users at once:

1. **Allow more instances:**

   ```bash
   gcloud run services update light-to-sheet \
     --region us-central1 \
     --max-instances 10
   ```

2. **Add Google Cloud Storage** for output files (so downloads work across instances). This requires code changes to `app.py` — upload results to a GCS bucket instead of `/tmp/`.

3. **Add rate limiting** per user with Firestore (Firebase's database) to prevent abuse.

4. **Set a minimum instance** to avoid cold starts (costs money but eliminates the 10-30s delay):

   ```bash
   gcloud run services update light-to-sheet \
     --region us-central1 \
     --min-instances 1
   ```

---

## Useful Commands Reference

```bash
# Check your deployment status
gcloud run services describe light-to-sheet --region us-central1

# View live logs
gcloud run services logs read light-to-sheet --region us-central1 --limit 50

# Stream logs in real-time
gcloud run services logs tail light-to-sheet --region us-central1

# Delete the service (stop all costs)
gcloud run services delete light-to-sheet --region us-central1

# List all deployed services
gcloud run services list
```

---

## Local Development

To run the app locally without Firebase credentials (auth will be bypassed):

```bash
DEBUG=1 python app.py
```

To run locally WITH Firebase auth:

1. Go to Firebase Console > Project Settings > Service Accounts
2. Click **Generate new private key** > **Generate key**
3. Save the JSON file somewhere safe (do NOT commit it to git)
4. Set the environment variable:

   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your-service-account-key.json"
   DEBUG=1 python app.py
   ```
