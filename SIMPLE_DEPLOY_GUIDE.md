# Simple Step-by-Step Deployment Guide

## Part 1: Deploy Frontend to Firebase (5 minutes)

### Step 1: Open Terminal
Open your Terminal application and navigate to your project:
```bash
cd /Users/zackram/invoice-reconciliation-platform
```

### Step 2: Login to Firebase
Run this command and follow the browser prompts:
```bash
npx firebase-tools@13.0.0 login
```
- It will open your browser
- Sign in with your Google account
- Click "Allow" when asked for permissions
- You'll see "Success! Logged in" in the terminal

### Step 3: Deploy the Frontend
Run the deployment script:
```bash
./deploy.sh
```

### Step 4: View Your Live Website
After deployment completes, open your browser and go to:
```
https://contractrecplatform.web.app
```

✅ **Your frontend is now live!** But it needs a backend to work properly.

---

## Part 2: Run Backend Locally for Testing (5 minutes)

### Step 1: Install Python Dependencies
In your terminal, run:
```bash
pip install -r requirements.txt
```

### Step 2: Create Environment File
```bash
cp .env.example .env
```

### Step 3: Add Your OpenAI API Key
Open the `.env` file in any text editor and replace:
```
OPENAI_API_KEY=your_openai_api_key_here
```
with your actual OpenAI API key:
```
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxx
```

### Step 4: Start the Backend Server
```bash
cd backend
python app.py
```

You should see:
```
* Running on http://127.0.0.1:5000
```

### Step 5: Test the Complete Application
1. Keep the backend running in terminal
2. Open a browser and go to: `http://localhost:5000`
3. Upload a contract and invoice PDF to test

---

## Part 3: Deploy Backend to the Cloud (Optional - 10 minutes)

Since Firebase doesn't easily support Python backends with OCR, use **Render** (free and simple):

### Step 1: Sign up for Render
1. Go to https://render.com
2. Sign up with your GitHub account

### Step 2: Create New Web Service
1. Click "New +" → "Web Service"
2. Connect your GitHub repository: `zramsky/invoice-reconciliation-platform`
3. Fill in these settings:
   - **Name**: `invoice-reconciliation-backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `cd backend && gunicorn app:app`

### Step 3: Add Environment Variables
In Render dashboard, add:
- **Key**: `OPENAI_API_KEY`
- **Value**: Your OpenAI API key

### Step 4: Add Tesseract Installation
Create a file called `build.sh` in your project:
```bash
#!/usr/bin/env bash
apt-get update
apt-get install -y tesseract-ocr poppler-utils
pip install -r requirements.txt
```

Update Render's Build Command to: `chmod +x build.sh && ./build.sh`

### Step 5: Deploy
Click "Create Web Service" and wait for deployment (takes 5-10 minutes)

### Step 6: Update Frontend API URL
Once deployed, Render will give you a URL like: `https://invoice-reconciliation-backend.onrender.com`

Edit `frontend/app.js` and change:
```javascript
const API_BASE = window.location.hostname === 'localhost' 
    ? 'http://localhost:5000/api' 
    : 'https://invoice-reconciliation-backend.onrender.com/api';
```

### Step 7: Redeploy Frontend
```bash
./deploy.sh
```

---

## ✅ You're Done!

Your complete application is now live:
- **Frontend**: https://contractrecplatform.web.app
- **Backend**: https://invoice-reconciliation-backend.onrender.com (or running locally)

## Testing Your Application

1. Go to https://contractrecplatform.web.app
2. Upload a contract PDF
3. Upload an invoice PDF
4. Click "Start Reconciliation"
5. View the AI-powered comparison results

## Troubleshooting

**"Command not found" errors:**
- Make sure you're in the right directory: `/Users/zackram/invoice-reconciliation-platform`

**"Permission denied" for deploy.sh:**
```bash
chmod +x deploy.sh
```

**Backend not working:**
- Check if your OpenAI API key is correct in `.env`
- Make sure Tesseract is installed: `brew install tesseract`

**Can't login to Firebase:**
- Try: `npx firebase-tools@13.0.0 login --reauth`

**Files not uploading:**
- Check file size (max 10MB by default)
- Ensure files are PDF or image format

## Need Help?

If something doesn't work:
1. Check the error message
2. Try the troubleshooting steps above
3. The backend might take 30 seconds to wake up on free hosting

---

## Quick Commands Reference

```bash
# Navigate to project
cd /Users/zackram/invoice-reconciliation-platform

# Deploy frontend
./deploy.sh

# Run backend locally
cd backend && python app.py

# View logs
npx firebase-tools@13.0.0 functions:log

# Check deployment status
npx firebase-tools@13.0.0 hosting:sites
```