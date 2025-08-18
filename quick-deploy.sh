#!/bin/bash

echo "🚀 Quick Production Deployment"
echo "=============================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Prerequisites Check:${NC}"
echo "✅ Railway CLI installed"
echo "✅ Vercel CLI installed"
echo "✅ Python 3 installed"
echo "✅ GitHub repo ready"
echo ""

echo -e "${YELLOW}Step 1: Railway Backend Deployment${NC}"
echo "1. This will open your browser to authenticate"
echo "2. Create a new project when prompted"
echo "3. Select 'Deploy from GitHub repo'"
echo ""
read -p "Press Enter to login to Railway..." 

railway login --browserless

echo ""
echo -e "${GREEN}✅ Railway login complete!${NC}"
echo ""

echo -e "${YELLOW}Step 2: Initialize Railway Project${NC}"
echo "Creating new Railway project..."
railway init

echo ""
echo -e "${YELLOW}Step 3: Add PostgreSQL Database${NC}"
echo "Run this command in Railway dashboard:"
echo -e "${BLUE}railway add${NC}"
echo "Then select 'PostgreSQL' from the list"
echo ""
read -p "Press Enter after adding PostgreSQL..."

echo ""
echo -e "${YELLOW}Step 4: Deploy Backend to Railway${NC}"
railway up

echo ""
echo -e "${GREEN}✅ Backend deployed!${NC}"
echo ""

# Get Railway URL
echo "Getting your Railway backend URL..."
RAILWAY_URL=$(railway status --json | grep -o '"domain":"[^"]*' | cut -d'"' -f4)
if [ -z "$RAILWAY_URL" ]; then
    echo "Please get your Railway URL from the dashboard"
    read -p "Enter your Railway URL (e.g., your-app.railway.app): " RAILWAY_URL
fi

echo "Railway Backend URL: https://$RAILWAY_URL"

echo ""
echo -e "${YELLOW}Step 5: Update Frontend Configuration${NC}"
# Update the frontend config with Railway URL
sed -i.bak "s|const railwayBackendUrl = '[^']*'|const railwayBackendUrl = 'https://$RAILWAY_URL'|" frontend/config.js
echo "✅ Frontend config updated with Railway URL"

echo ""
echo -e "${YELLOW}Step 6: Deploy Frontend to Vercel${NC}"
echo "1. This will open your browser"
echo "2. Import your GitHub repository"
echo "3. Keep all default settings"
echo ""
read -p "Press Enter to deploy to Vercel..."

vercel --prod

echo ""
echo -e "${GREEN}🎉 DEPLOYMENT COMPLETE!${NC}"
echo ""
echo "📋 Your Live URLs:"
echo "Backend API: https://$RAILWAY_URL"
echo "Frontend: Check Vercel output above"
echo ""
echo "🧪 Test your deployment:"
echo "1. Backend Health: curl https://$RAILWAY_URL/api/health"
echo "2. Visit your Vercel frontend URL"
echo "3. Run: ./test-production.sh"
echo ""
echo "📊 Monitor your app:"
echo "Railway Dashboard: https://railway.app/dashboard"
echo "Vercel Dashboard: https://vercel.com/dashboard"