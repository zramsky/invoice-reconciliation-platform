# Firebase Deployment Setup Guide

## Quick Setup Instructions

Since you have Node.js v19.3.0 (Firebase CLI requires v20+), we'll use `npx` to run Firebase commands.

## Step 1: Login to Firebase

Run this command and follow the browser prompts:

```bash
npx firebase-tools@13.0.0 login
```

This will open your browser. Log in with your Google account.

## Step 2: Create a Firebase Project

Option A - Via Firebase Console (Recommended):
1. Go to https://console.firebase.google.com/
2. Click "Create a project"
3. Name it: "invoice-reconciliation-platform"
4. Disable Google Analytics (optional)
5. Click "Create Project"

Option B - Via CLI:
```bash
npx firebase-tools@13.0.0 projects:create invoice-reconciliation-platform
```

## Step 3: Initialize Firebase in your project

```bash
cd /Users/zackram/invoice-reconciliation-platform
npx firebase-tools@13.0.0 init hosting
```

When prompted:
- Use an existing project → Select your project
- Public directory: `frontend`
- Configure as single-page app: No
- Set up automatic builds with GitHub: No (we can do this later)

## Step 4: Deploy to Firebase Hosting

```bash
npx firebase-tools@13.0.0 deploy --only hosting
```

## Step 5: View your deployed app

After deployment, you'll get a URL like:
`https://invoice-reconciliation-platform.web.app`

## Alternative: Deploy Backend to Cloud Run

Since Firebase Functions require specific Node versions and Python functions have limitations, consider deploying the backend separately:

### Option 1: Deploy Backend on Cloud Run

1. Create a Dockerfile for the backend:

```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
RUN pip install gunicorn

COPY backend/ ./backend/
COPY .env.example .env

WORKDIR /app/backend
EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "2", "--timeout", "120", "app:app"]
```

2. Deploy to Google Cloud Run:
```bash
gcloud run deploy invoice-backend \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars OPENAI_API_KEY=your-key-here
```

3. Update frontend to use Cloud Run URL:
Edit `frontend/app.js` and update the API_BASE to your Cloud Run URL.

### Option 2: Use Vercel for Backend

1. Create `vercel.json`:
```json
{
  "version": 2,
  "builds": [
    {
      "src": "backend/app.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/api/(.*)",
      "dest": "backend/app.py"
    }
  ]
}
```

2. Deploy with Vercel CLI:
```bash
npm i -g vercel
vercel
```

## Current Status

✅ Frontend is ready for Firebase Hosting
✅ Project structure is configured
⏳ Awaiting Firebase login and project creation
⏳ Backend deployment needs separate solution (Cloud Run or Vercel recommended)

## Next Steps

1. Run `npx firebase-tools@13.0.0 login`
2. Create project in Firebase Console
3. Deploy frontend: `npx firebase-tools@13.0.0 deploy --only hosting`
4. Choose backend deployment option (Cloud Run or Vercel)

## Important Notes

- The frontend will work on Firebase Hosting
- The backend needs a separate deployment due to Python requirements
- OCR (Tesseract) requires system dependencies that Firebase Functions doesn't easily support
- Cloud Run or Vercel are better options for the Python backend