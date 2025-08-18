# 🚂 Railway Deployment Instructions

## Step 1: Delete Current Project
1. Go to https://railway.app/dashboard
2. Find "invoice-reconciliation-backend" project
3. Click Settings → Danger → Delete Project

## Step 2: Create New Project from GitHub
1. Click "New Project"
2. Select "Deploy from GitHub repo"
3. Choose: zramsky/invoice-reconciliation-platform
4. Wait for deployment to complete

## Step 3: Add PostgreSQL Database
1. In your project dashboard, click "New Service"
2. Select "Database" → "PostgreSQL" 
3. Wait 2-3 minutes for provisioning

## Step 4: Configure Environment Variables
1. Click on your main service (not the database)
2. Go to "Variables" tab
3. Add these variables:
   - PORT = $PORT (Railway auto-sets this)
   - UPLOAD_FOLDER = uploads
   - MAX_FILE_SIZE = 10485760

## Step 5: Get Your URL
1. Go to "Settings" tab of your main service
2. Under "Domains", you'll see your Railway URL
3. It should look like: https://web-production-XXXX.up.railway.app

## Step 6: Test
Visit: https://your-railway-url.up.railway.app/api/ping
Should return: {"status":"ok","timestamp":"..."}