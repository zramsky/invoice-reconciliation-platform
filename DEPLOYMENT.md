# Deployment Guide

This guide covers deployment options for the Invoice Reconciliation Platform.

## Local Development

### Prerequisites
- Python 3.8+
- Tesseract OCR
- OpenAI API key

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your OpenAI API key

# Run the application
cd backend
python app.py
```

Access at: http://localhost:5000

## Firebase Deployment

### Prerequisites
- Firebase CLI installed (`npm install -g firebase-tools`)
- Google Cloud account
- OpenAI API key

### Initial Setup

1. **Install Firebase Tools:**
```bash
npm install -g firebase-tools
```

2. **Login to Firebase:**
```bash
firebase login
```

3. **Initialize Firebase Project:**
```bash
firebase init
# Select: Hosting, Functions
# Choose existing project or create new
# Python for Functions runtime
```

4. **Set Environment Variables:**
```bash
firebase functions:config:set openai.key="your-openai-api-key"
```

### Deploy to Firebase

1. **Install dependencies:**
```bash
npm install
```

2. **Deploy everything:**
```bash
npm run deploy
```

Or deploy separately:
```bash
# Deploy hosting only
npm run deploy:hosting

# Deploy functions only
npm run deploy:functions
```

3. **Access your app:**
```
https://your-project-id.web.app
```

### Firebase Configuration

The project includes:
- `firebase.json` - Firebase hosting and functions configuration
- `firebase-functions/` - Python Cloud Functions
- `package.json` - Deployment scripts

## Alternative Deployment Options

### 1. Heroku Deployment

Create `Procfile`:
```
web: gunicorn --chdir backend app:app
```

Deploy:
```bash
heroku create your-app-name
heroku config:set OPENAI_API_KEY=your-key
git push heroku main
```

### 2. Google Cloud Run

Create `Dockerfile`:
```dockerfile
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
WORKDIR /app/backend

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "app:app"]
```

Deploy:
```bash
gcloud run deploy invoice-reconciliation \
  --source . \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

### 3. AWS Lambda + S3

Use Zappa for serverless deployment:
```bash
pip install zappa
zappa init
zappa deploy production
```

## Environment Variables

Required for all deployments:
- `OPENAI_API_KEY` - Your OpenAI API key
- `UPLOAD_FOLDER` - Directory for uploads (default: uploads)
- `PROCESSED_FOLDER` - Directory for processed files (default: processed)
- `MAX_FILE_SIZE` - Maximum upload size in bytes (default: 10485760)

## Security Considerations

1. **API Keys:**
   - Never commit `.env` files
   - Use environment variables in production
   - Rotate keys regularly

2. **File Uploads:**
   - Implement file size limits
   - Validate file types
   - Use virus scanning in production

3. **CORS:**
   - Configure allowed origins for production
   - Don't use wildcard (*) in production

4. **Authentication:**
   - Add user authentication for production
   - Implement rate limiting
   - Use HTTPS only

## Monitoring

### Firebase Monitoring
- View logs: `firebase functions:log`
- Firebase Console: Analytics, Performance, Crashlytics

### Custom Monitoring
Add logging to track:
- Processing times
- Error rates
- API usage
- User activity

## Scaling Considerations

1. **Firebase Functions:**
   - Cold starts may affect performance
   - Consider minimum instances for production
   - Monitor execution time and memory

2. **OCR Processing:**
   - CPU intensive - consider dedicated processing service
   - Implement queuing for large files
   - Cache results when possible

3. **API Rate Limits:**
   - OpenAI has rate limits
   - Implement retry logic
   - Consider caching AI responses

## Troubleshooting

### Common Issues

1. **Tesseract not found:**
   - Ensure Tesseract is installed in deployment environment
   - Update Docker/deployment scripts to include Tesseract

2. **PDF processing errors:**
   - Install poppler-utils
   - Check file permissions

3. **CORS errors:**
   - Update allowed origins in Flask/Firebase config
   - Check browser console for specific errors

4. **Memory issues:**
   - Increase function memory allocation
   - Process large files in chunks
   - Implement file size limits

## Cost Optimization

1. **Firebase:**
   - Use Firebase Spark (free) tier for testing
   - Monitor usage in Firebase Console
   - Optimize function execution time

2. **OpenAI API:**
   - Use GPT-3.5-turbo (cheaper than GPT-4)
   - Implement caching for similar documents
   - Batch process when possible

## Support

For issues or questions:
- GitHub Issues: https://github.com/zramsky/invoice-reconciliation-platform/issues
- Documentation: See README.md