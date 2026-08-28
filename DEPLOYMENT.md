# RoleRunner — Production Deployment & Feedback Setup

This guide provides the easiest and fastest way to deploy **RoleRunner** into production so external users and testers can use the platform and submit feedback.

---

## 🚀 Recommended Deployment: Railway or Render (Zero DevOps)

### Option 1: Deploy on Railway (Easiest — ~2 minutes)

1. Go to [Railway.app](https://railway.app) and log in with your GitHub account.
2. Click **"New Project"** $\rightarrow$ **"Deploy from GitHub repo"** $\rightarrow$ Select `cosminmarian53/RoleRunner`.
3. In the Railway project canvas:
   - Click **+ New** $\rightarrow$ **Database** $\rightarrow$ Add **PostgreSQL**.
   - Click **+ New** $\rightarrow$ **Database** $\rightarrow$ Add **Redis**.
4. In your RoleRunner service settings, set the following Environment Variables:
   - `DATABASE_URL`: `${{Postgres.DATABASE_URL}}`
   - `REDIS_URL`: `${{Redis.REDIS_URL}}`
   - `APP_ENV`: `production`
   - `FEEDBACK_WEBHOOK_URL`: `https://discord.com/api/webhooks/...` *(Optional: your Discord/Slack channel webhook)*
5. Click **"Generate Domain"** under Networking to get your public HTTPS URL (e.g. `https://rolerunner-production.up.railway.app`).
6. Every git push to `main` will automatically build and deploy!

---

### Option 2: Deploy on Render (Free Blueprint — ~3 minutes)

1. Go to [Render.com](https://render.com) and click **"New +"** $\rightarrow$ **"Blueprint"**.
2. Connect your GitHub repository `cosminmarian53/RoleRunner`.
3. Render will automatically read [`render.yaml`](file:///Users/lavriccosmin/For%20jobs/job-bot/render.yaml) and spin up:
   - `rolerunner-api` (FastAPI Docker container)
   - `rolerunner-frontend` (Vite / Tailwind static edge build)
   - `rolerunner-db` (Managed PostgreSQL 16)
   - `rolerunner-redis` (Managed Redis cache & worker broker)
4. Click **Apply** to deploy!

---

## 💬 Real-Time Feedback Alerts Setup

RoleRunner includes a built-in user feedback widget (`💡 Give Feedback`). Whenever a user submits a rating, idea, or bug report:

1. **Discord Channel Alert**:
   - Create a webhook in any Discord channel (*Channel Settings* $\rightarrow$ *Integrations* $\rightarrow$ *Webhooks* $\rightarrow$ *New Webhook*).
   - Set the `FEEDBACK_WEBHOOK_URL` environment variable in your production host.
   - You will receive instant push notifications on your phone whenever anyone leaves feedback.
2. **PostgreSQL Persistence**:
   - All submissions are stored in the backend and logged under `/api/feedback`.
