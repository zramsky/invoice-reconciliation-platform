// Backend Configuration
const BackendConfig = {
    // Automatically detect environment and use appropriate backend
    getBackendUrl: () => {
        // If running locally (localhost or 127.0.0.1), use local backend
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            return 'http://localhost:5001';
        }
        
        // For production, try these backends in order:
        // 1. Railway (fastest startup)
        // 2. Fly.io (backup)
        // 3. Fall back to local storage only mode
        
        // Try Railway first (better cold start performance)
        const railwayBackendUrl = 'https://web-production-1a9f2.up.railway.app';
        const flyBackendUrl = 'https://invoice-reconciliation-backend.fly.dev';
        
        // Check if we have a Railway deployment (update this URL when deployed)
        const deployedBackendUrl = railwayBackendUrl || flyBackendUrl;
        
        if (deployedBackendUrl) {
            return deployedBackendUrl;
        }
        
        // No backend available - using localStorage only
        return null;
    },
    
    // Check if backend is available
    isBackendAvailable: async () => {
        const url = BackendConfig.getBackendUrl();
        if (!url) return false;
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000);
            
            const response = await fetch(`${url}/api/ping`, {
                method: 'GET',
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            return response.ok;
        } catch (error) {
            console.warn('Backend not available:', error);
            return false;
        }
    },
    
    // Get storage mode (backend or localStorage)
    getStorageMode: async () => {
        const backendAvailable = await BackendConfig.isBackendAvailable();
        return backendAvailable ? 'backend' : 'localStorage';
    },
    
    // Make API request with retry logic
    makeRequest: async (endpoint, options = {}) => {
        const url = BackendConfig.getBackendUrl();
        if (!url) throw new Error('Backend not available');
        
        const maxRetries = 3;
        let lastError;
        
        for (let i = 0; i < maxRetries; i++) {
            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 30000);
                
                const response = await fetch(`${url}${endpoint}`, {
                    ...options,
                    signal: controller.signal
                });
                clearTimeout(timeoutId);
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                return response;
            } catch (error) {
                lastError = error;
                if (i < maxRetries - 1) {
                    console.log(`API request failed, retrying... (${i + 1}/${maxRetries})`);
                    await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1))); // Exponential backoff
                }
            }
        }
        
        throw lastError;
    }
};

// Export for use in other files
window.BackendConfig = BackendConfig;