# 🏢 Invoice Reconciliation Platform

> **AI-powered contract and invoice reconciliation platform with advanced OCR and GPT-4 Vision analysis**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Firebase Deployment](https://img.shields.io/badge/Deployed%20on-Firebase-orange.svg)](https://contractrecplatform.web.app)
[![AI Powered](https://img.shields.io/badge/AI-GPT--4%20Vision-blue.svg)](https://openai.com)

## 🌟 Overview

The Invoice Reconciliation Platform is a modern, AI-powered web application that automates the complex process of contract and invoice reconciliation. By leveraging OCR technology and GPT-4 Vision AI, it extracts, analyzes, and compares contract terms with invoices to identify discrepancies and ensure billing accuracy.

### ✨ Key Features

- **🔍 AI-Powered Analysis**: GPT-4 Vision for comprehensive document analysis including tables and structured data
- **📄 Smart OCR Processing**: Advanced text extraction from PDFs, images, and Word documents
- **⚡ Real-time Validation**: Live form validation and file processing with immediate feedback
- **💾 Auto-save Drafts**: Automatic draft saving with 24-hour retention for data loss prevention
- **🔄 Duplicate Detection**: Smart vendor duplicate prevention with user confirmation
- **📊 Professional Dashboard**: Comprehensive vendor management with KPI tracking
- **🎯 Progress Control**: Cancellable operations with detailed progress indicators
- **🛡️ Enhanced Security**: Client-side processing with secure API key management

## 🚀 Quick Start

### Live Demo
**🔗 [Try it now: https://contractrecplatform.web.app](https://contractrecplatform.web.app)**

### Prerequisites
- Web browser (Chrome, Firefox, Safari, Edge)
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

### Setup Instructions

1. **Access the Platform**
   ```
   https://contractrecplatform.web.app
   ```

2. **Configure API Key**
   - Click the Settings gear icon
   - Enter your OpenAI API key
   - Key is stored securely in your browser

3. **Start Using**
   - Upload contract documents (PDF, Word, Images)
   - AI automatically extracts vendor information
   - Review and confirm vendor details
   - Track all vendors in the dashboard

## 📁 Project Structure

```
invoice-reconciliation-platform/
├── 📂 frontend/                 # Main web application
│   ├── index.html              # Dashboard and main interface
│   ├── add-vendor.html         # Vendor creation workflow
│   └── vendor-profile.html     # Individual vendor management
├── 📂 backend/                 # Python backend services (optional)
│   ├── app.py                  # Flask application
│   ├── models.py               # Data models
│   ├── services.py             # Business logic
│   └── api.py                  # API endpoints
├── 📂 docs/                    # Documentation
│   ├── DEPLOYMENT.md           # Deployment guide
│   ├── FIREBASE_SETUP.md       # Firebase configuration
│   └── HOW_TO_USE.md          # User guide
├── 📂 firebase-functions/      # Firebase cloud functions
├── deploy.sh                   # Deployment script
├── firebase.json              # Firebase configuration
└── README.md                  # This file
```

## 🔧 Technology Stack

### Frontend
- **HTML5 + CSS3**: Modern responsive design
- **Vanilla JavaScript**: No framework dependencies
- **PDF.js**: Client-side PDF processing
- **Tesseract.js**: OCR processing capabilities

### AI & Processing
- **OpenAI GPT-4**: Text analysis and extraction
- **GPT-4 Vision**: Image and document analysis
- **Custom Prompts**: Specialized for contract analysis

### Deployment
- **Firebase Hosting**: Global CDN deployment
- **GitHub Pages**: Alternative hosting option
- **Docker**: Containerized deployment support

## 📖 Usage Guide

### Adding Vendors

1. **Upload Contract**
   - Drag & drop or click to select files
   - Supports: PDF, Word docs, Images (up to 50MB)
   - Real-time file validation and preview

2. **AI Analysis**
   - Automatic text extraction via OCR
   - GPT-4 Vision analyzes tables and structured data
   - Progress indicator with cancellation option

3. **Review & Save**
   - AI pre-fills vendor information
   - Real-time form validation
   - Auto-save drafts prevent data loss
   - Duplicate detection prevents conflicts

### Managing Vendors

- **Dashboard Overview**: View all active vendors and KPIs
- **Search & Filter**: Find vendors quickly
- **Vendor Profiles**: Detailed view with contract terms
- **Invoice Upload**: Add invoices for reconciliation

## 🛠️ Development

### Local Development Setup

1. **Clone Repository**
   ```bash
   git clone https://github.com/zramsky/invoice-reconciliation-platform.git
   cd invoice-reconciliation-platform
   ```

2. **Serve Frontend**
   ```bash
   # Using Python
   python -m http.server 8000
   
   # Using Node.js
   npx serve frontend
   
   # Using live-server
   npx live-server frontend
   ```

3. **Access Application**
   ```
   http://localhost:8000
   ```

### Firebase Deployment

1. **Install Firebase CLI**
   ```bash
   npm install -g firebase-tools
   ```

2. **Deploy**
   ```bash
   ./deploy.sh
   ```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for detailed deployment instructions.

## 📊 Features in Detail

### AI-Powered Document Analysis
- **Multi-format Support**: PDF, Word, JPEG, PNG, TIFF
- **Table Recognition**: Extracts data from structured tables
- **Vision Processing**: Analyzes charts, layouts, and visual elements
- **Smart Fallbacks**: Text analysis when vision processing unavailable

### User Experience Enhancements
- **Real-time Validation**: Immediate feedback on form inputs
- **Progress Cancellation**: Stop long-running operations
- **Auto-save Drafts**: Preserve work automatically
- **File Preview**: Confirm uploads before processing
- **Professional Loading States**: Clear feedback during operations

### Data Management
- **Local Storage**: Client-side data persistence
- **Duplicate Prevention**: Smart vendor conflict detection
- **Export Capabilities**: Download vendor data
- **Backup Support**: Manual data export/import

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/zramsky/invoice-reconciliation-platform/issues)
- **Live Demo**: [contractrecplatform.web.app](https://contractrecplatform.web.app)

## 🔮 Roadmap

- [ ] **Mobile App**: Native iOS/Android applications
- [ ] **API Integration**: RESTful API for third-party integrations
- [ ] **Advanced Analytics**: Detailed reconciliation reporting
- [ ] **Multi-tenant Support**: Organization and team management
- [ ] **Automated Workflows**: Scheduled reconciliation processes
- [ ] **Advanced Security**: SSO, role-based access control

---

**Made with ❤️ for modern businesses seeking automated invoice reconciliation**