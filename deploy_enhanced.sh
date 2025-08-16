#!/bin/bash

echo "🚀 Unspend Platform Enhanced Deployment"
echo "======================================="
echo ""

# Configuration
PROJECT_ID="unspend-91424"
ENVIRONMENT=${1:-production}
RUN_TESTS=${2:-true}

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Error handling
set -e
trap 'echo -e "${RED}❌ Deployment failed at line $LINENO${NC}"' ERR

# Function to check prerequisites
check_prerequisites() {
    echo -e "${BLUE}📋 Checking prerequisites...${NC}"
    
    # Check Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${RED}❌ Node.js is not installed${NC}"
        exit 1
    fi
    
    # Check Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is not installed${NC}"
        exit 1
    fi
    
    # Check Firebase CLI
    if ! npx firebase-tools@13.0.0 --version &> /dev/null; then
        echo -e "${YELLOW}⚠️  Installing Firebase CLI...${NC}"
        npm install -g firebase-tools@13.0.0
    fi
    
    echo -e "${GREEN}✅ Prerequisites check passed${NC}"
    echo ""
}

# Function to run tests
run_tests() {
    if [ "$RUN_TESTS" = "true" ]; then
        echo -e "${BLUE}🧪 Running tests...${NC}"
        
        if [ -f "run_tests.sh" ]; then
            ./run_tests.sh
            if [ $? -ne 0 ]; then
                echo -e "${RED}❌ Tests failed. Aborting deployment.${NC}"
                exit 1
            fi
        else
            echo -e "${YELLOW}⚠️  No test script found, skipping tests${NC}"
        fi
        echo ""
    fi
}

# Function to build frontend
build_frontend() {
    echo -e "${BLUE}🏗️  Building frontend...${NC}"
    
    # Minify JavaScript if tools available
    if command -v terser &> /dev/null; then
        for file in frontend/*.js; do
            if [ -f "$file" ]; then
                echo "Minifying $(basename $file)..."
                terser "$file" -o "$file.min.js" --compress --mangle
            fi
        done
    fi
    
    # Optimize images if tools available
    if command -v optipng &> /dev/null; then
        find frontend -name "*.png" -exec optipng -o5 {} \;
    fi
    
    echo -e "${GREEN}✅ Frontend build complete${NC}"
    echo ""
}

# Function to validate configuration
validate_config() {
    echo -e "${BLUE}🔍 Validating configuration...${NC}"
    
    # Check firebase.json
    if [ ! -f "firebase.json" ]; then
        echo -e "${RED}❌ firebase.json not found${NC}"
        exit 1
    fi
    
    # Check .firebaserc
    if [ ! -f ".firebaserc" ]; then
        echo -e "${RED}❌ .firebaserc not found${NC}"
        exit 1
    fi
    
    # Validate JSON syntax
    python3 -m json.tool firebase.json > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo -e "${RED}❌ Invalid firebase.json${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Configuration valid${NC}"
    echo ""
}

# Function to check Firebase auth
check_firebase_auth() {
    echo -e "${BLUE}🔐 Checking Firebase authentication...${NC}"
    
    npx firebase-tools@13.0.0 login:list > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}⚠️  Not logged in to Firebase${NC}"
        echo "Please run: npx firebase-tools@13.0.0 login"
        exit 1
    fi
    
    echo -e "${GREEN}✅ Firebase authentication confirmed${NC}"
    echo ""
}

# Function to create deployment backup
create_backup() {
    echo -e "${BLUE}💾 Creating deployment backup...${NC}"
    
    BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Backup frontend
    cp -r frontend "$BACKUP_DIR/"
    
    # Backup configuration
    cp firebase.json "$BACKUP_DIR/"
    cp .firebaserc "$BACKUP_DIR/"
    
    echo -e "${GREEN}✅ Backup created at $BACKUP_DIR${NC}"
    echo ""
}

# Function to deploy to Firebase
deploy_firebase() {
    echo -e "${BLUE}🚀 Deploying to Firebase ($ENVIRONMENT)...${NC}"
    
    if [ "$ENVIRONMENT" = "staging" ]; then
        # Deploy to staging channel
        npx firebase-tools@13.0.0 hosting:channel:deploy staging \
            --project "$PROJECT_ID" \
            --expires 7d
        
        echo -e "${GREEN}✅ Deployed to staging channel${NC}"
        echo -e "${BLUE}Preview URL: https://${PROJECT_ID}--staging-web.app${NC}"
    else
        # Deploy to production
        npx firebase-tools@13.0.0 deploy \
            --only hosting \
            --project "$PROJECT_ID"
        
        echo -e "${GREEN}✅ Deployed to production${NC}"
        echo -e "${BLUE}Live URLs:${NC}"
        echo "   https://${PROJECT_ID}.web.app"
        echo "   https://${PROJECT_ID}.firebaseapp.com"
    fi
    echo ""
}

# Function to run post-deployment tests
post_deployment_tests() {
    echo -e "${BLUE}🔍 Running post-deployment tests...${NC}"
    
    if [ "$ENVIRONMENT" = "staging" ]; then
        URL="https://${PROJECT_ID}--staging-web.app"
    else
        URL="https://${PROJECT_ID}.web.app"
    fi
    
    # Test if site is accessible
    if curl -s -o /dev/null -w "%{http_code}" "$URL" | grep -q "200"; then
        echo -e "${GREEN}✅ Site is accessible${NC}"
    else
        echo -e "${RED}❌ Site is not accessible${NC}"
        exit 1
    fi
    
    echo ""
}

# Function to update deployment status
update_status() {
    echo -e "${BLUE}📝 Updating deployment status...${NC}"
    
    # Update deployment log
    echo "$(date '+%Y-%m-%d %H:%M:%S') - Deployed to $ENVIRONMENT by Infrastructure Instance" >> deployment.log
    
    # Update CLAUDE.md activity log
    if [ -f "CLAUDE.md" ]; then
        sed -i.bak '/### Activity Log/a\
- Infrastructure Instance: Deployed to '"$ENVIRONMENT"' environment ('"$(date '+%Y-%m-%d %H:%M')"')' CLAUDE.md
    fi
    
    echo -e "${GREEN}✅ Status updated${NC}"
    echo ""
}

# Main deployment flow
main() {
    echo "Environment: $ENVIRONMENT"
    echo "Run Tests: $RUN_TESTS"
    echo ""
    
    check_prerequisites
    validate_config
    check_firebase_auth
    
    if [ "$RUN_TESTS" = "true" ]; then
        run_tests
    fi
    
    create_backup
    build_frontend
    deploy_firebase
    post_deployment_tests
    update_status
    
    echo -e "${GREEN}🎉 Deployment completed successfully!${NC}"
    echo ""
    echo "📊 Deployment Summary:"
    echo "   Environment: $ENVIRONMENT"
    echo "   Project: $PROJECT_ID"
    echo "   Timestamp: $(date '+%Y-%m-%d %H:%M:%S')"
    
    if [ "$ENVIRONMENT" = "staging" ]; then
        echo "   Preview URL: https://${PROJECT_ID}--staging-web.app"
    else
        echo "   Production URLs:"
        echo "     - https://${PROJECT_ID}.web.app"
        echo "     - https://${PROJECT_ID}.firebaseapp.com"
    fi
}

# Run main function
main