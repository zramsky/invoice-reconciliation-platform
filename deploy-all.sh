#!/bin/bash

echo "🚀 Deploying Invoice Reconciliation Platform"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "app.py" ] || [ ! -d "frontend" ]; then
    print_error "Please run this script from the invoice-reconciliation-platform directory"
    exit 1
fi

print_status "Step 1: Preparing deployment files..."

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    print_warning "Creating .env file from template"
    cp .env.example .env
fi

# Install Python dependencies locally for testing
print_status "Step 2: Installing Python dependencies..."
pip3 install -r requirements.txt

# Test the backend locally
print_status "Step 3: Testing backend locally..."
export FLASK_ENV=development
export UPLOAD_FOLDER=uploads
export MAX_FILE_SIZE=10485760

# Start backend in background
python3 app.py &
BACKEND_PID=$!
print_status "Backend started with PID: $BACKEND_PID"

# Wait for backend to start
sleep 3

# Test backend endpoints
print_status "Testing backend endpoints..."

# Test ping endpoint
PING_RESPONSE=$(curl -s -w "%{http_code}" http://localhost:5001/api/ping)
PING_CODE="${PING_RESPONSE: -3}"
if [ "$PING_CODE" = "200" ]; then
    print_success "✅ Ping endpoint working"
else
    print_error "❌ Ping endpoint failed (HTTP $PING_CODE)"
fi

# Test health endpoint
HEALTH_RESPONSE=$(curl -s -w "%{http_code}" http://localhost:5001/api/health)
HEALTH_CODE="${HEALTH_RESPONSE: -3}"
if [ "$HEALTH_CODE" = "200" ]; then
    print_success "✅ Health endpoint working"
else
    print_error "❌ Health endpoint failed (HTTP $HEALTH_CODE)"
fi

# Test vendors endpoint
VENDORS_RESPONSE=$(curl -s -w "%{http_code}" http://localhost:5001/api/vendors)
VENDORS_CODE="${VENDORS_RESPONSE: -3}"
if [ "$VENDORS_CODE" = "200" ]; then
    print_success "✅ Vendors API working"
else
    print_error "❌ Vendors API failed (HTTP $VENDORS_CODE)"
fi

# Test monitoring endpoints
MONITOR_RESPONSE=$(curl -s -w "%{http_code}" http://localhost:5001/api/monitor/health)
MONITOR_CODE="${MONITOR_RESPONSE: -3}"
if [ "$MONITOR_CODE" = "200" ]; then
    print_success "✅ Monitoring endpoints working"
else
    print_error "❌ Monitoring endpoints failed (HTTP $MONITOR_CODE)"
fi

# Stop the test backend
kill $BACKEND_PID
print_status "Stopped test backend"

print_status "Step 4: Committing latest changes..."

# Stage and commit all changes
git add .
git status

read -p "Commit changes to Git? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    git commit -m "🎯 Production-Ready Platform with Database & Monitoring

✨ Complete production setup:
• PostgreSQL database with SQLite fallback
• Comprehensive monitoring and health checks
• Performance profiling and metrics
• Railway deployment configuration
• Vercel frontend deployment setup
• Error handling and logging

🚀 Ready for deployment to Railway + Vercel

🔧 Generated with Claude Code

Co-Authored-By: Claude <noreply@anthropic.com>"
    
    git push origin main
    print_success "Changes pushed to GitHub"
else
    print_warning "Skipping Git commit"
fi

print_status "Step 5: Deployment instructions..."

echo ""
echo "🎯 DEPLOYMENT INSTRUCTIONS"
echo "========================="
echo ""
echo "📦 BACKEND (Railway):"
echo "1. Go to https://railway.app"
echo "2. Create new project from GitHub repo: $PWD"
echo "3. Add PostgreSQL database service"
echo "4. Set environment variables:"
echo "   - OPENAI_API_KEY (optional)"
echo "   - UPLOAD_FOLDER=uploads"
echo "   - MAX_FILE_SIZE=10485760"
echo "5. Deploy automatically via GitHub integration"
echo ""
echo "🌐 FRONTEND (Vercel):"
echo "1. Go to https://vercel.com"
echo "2. Create new project from GitHub repo: $PWD"
echo "3. Use settings from vercel.json"
echo "4. Deploy automatically"
echo ""
echo "🔄 POST-DEPLOYMENT:"
echo "1. Update frontend/config.js with Railway backend URL"
echo "2. Test all endpoints"
echo "3. Monitor via /api/monitor/health"
echo ""
echo "📊 MONITORING ENDPOINTS:"
echo "• Health: /api/health"
echo "• Detailed: /api/monitor/health"
echo "• Performance: /api/monitor/performance"
echo ""

# Check if Railway CLI is available
if command -v railway &> /dev/null; then
    echo "🚄 Railway CLI detected!"
    read -p "Deploy to Railway now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        railway login
        railway init
        railway up
        print_success "Deployed to Railway!"
    fi
else
    print_warning "Railway CLI not found. Install with: npm install -g @railway/cli"
fi

# Check if Vercel CLI is available
if command -v vercel &> /dev/null; then
    echo "⚡ Vercel CLI detected!"
    read -p "Deploy frontend to Vercel now? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        vercel --prod
        print_success "Deployed to Vercel!"
    fi
else
    print_warning "Vercel CLI not found. Install with: npm install -g vercel"
fi

print_success "🎉 Deployment preparation complete!"
echo ""
echo "Your platform is now ready for production with:"
echo "✅ Database persistence (PostgreSQL/SQLite)"
echo "✅ Performance monitoring"
echo "✅ Error handling and retries"
echo "✅ Security headers"
echo "✅ Health checks"
echo "✅ Auto-scaling configuration"
echo ""
echo "Next: Deploy to Railway + Vercel and update config URLs!"