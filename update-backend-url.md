# Update Backend URL After Deployment

## After you deploy the backend and get your URL:

1. **Edit frontend/add-vendor.html**:
   ```javascript
   // Line ~1714: Replace this line:
   'https://your-backend-url.herokuapp.com'; // TODO: Replace with actual deployed backend URL
   
   // With your actual Railway URL:
   'https://your-app.railway.app'; // Your actual deployed backend URL
   ```

2. **Deploy updated frontend**:
   ```bash
   firebase deploy
   ```

3. **Test the complete workflow**:
   - Visit https://contractrecplatform.web.app
   - Upload a vendor contract
   - Click "View Contract" - should open properly (no blank tabs!)

## Your URLs will be:
- **Frontend**: https://contractrecplatform.web.app (Firebase)
- **Backend**: https://your-app.railway.app (Railway/Render/Heroku)
- **API**: https://your-app.railway.app/api/vendors

## Benefits of This Setup:
✅ Proper file storage (no more base64 limitations)
✅ Scalable backend API
✅ Fast global frontend (Firebase CDN)
✅ Free hosting for both frontend and backend
✅ Professional contract viewing and downloading