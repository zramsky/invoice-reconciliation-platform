#!/bin/bash

echo "🚀 Firebase Deployment Script"
echo "=============================="
echo ""

# Check if user is logged in
echo "📋 Checking Firebase authentication..."
npx firebase-tools@13.0.0 login:list > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "❌ Not logged in to Firebase"
    echo "👉 Please run: npx firebase-tools@13.0.0 login"
    exit 1
fi

echo "✅ Firebase authentication confirmed"
echo ""

# Deploy to Firebase Hosting
echo "🌐 Deploying to Firebase Hosting..."
echo "Project: contractrecplatform"
echo ""

npx firebase-tools@13.0.0 deploy --only hosting --project contractrecplatform

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Deployment successful!"
    echo "🔗 Your app is now live at:"
    echo "   https://contractrecplatform.web.app"
    echo "   https://contractrecplatform.firebaseapp.com"
else
    echo ""
    echo "❌ Deployment failed. Please check the error messages above."
fi