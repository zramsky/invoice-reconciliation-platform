// API Configuration
const API_CONFIG = {
    BASE_URL: window.location.hostname === 'localhost' 
        ? 'http://localhost:5000' 
        : 'https://invoice-reconciliation-platform-vtb2.onrender.com',
    ENDPOINTS: {
        LOGIN: '/api/auth/login',
        REGISTER: '/api/auth/register',
        VERIFY: '/api/auth/verify',
        DASHBOARD: '/api/dashboard',
        UPLOAD_CONTRACT: '/api/contracts',
        UPLOAD_INVOICE: '/api/invoices',
        RECONCILE: '/api/reconcile'
    }
};

// API Helper functions
const API = {
    async post(endpoint, data, options = {}) {
        const url = `${API_CONFIG.BASE_URL}${endpoint}`;
        const config = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            body: JSON.stringify(data),
            ...options
        };
        
        const token = localStorage.getItem('token');
        if (token && token !== 'demo-token') {
            config.headers['Authorization'] = `Bearer ${token}`;
        }
        
        return fetch(url, config);
    },
    
    async get(endpoint, options = {}) {
        const url = `${API_CONFIG.BASE_URL}${endpoint}`;
        const config = {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };
        
        const token = localStorage.getItem('token');
        if (token && token !== 'demo-token') {
            config.headers['Authorization'] = `Bearer ${token}`;
        }
        
        return fetch(url, config);
    },
    
    async upload(endpoint, formData, options = {}) {
        const url = `${API_CONFIG.BASE_URL}${endpoint}`;
        const config = {
            method: 'POST',
            body: formData,
            ...options
        };
        
        const token = localStorage.getItem('token');
        if (token && token !== 'demo-token') {
            config.headers = {
                'Authorization': `Bearer ${token}`,
                ...options.headers
            };
        }
        
        return fetch(url, config);
    }
};

// Export for global access
window.API_CONFIG = API_CONFIG;
window.API = API;