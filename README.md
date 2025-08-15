# Invoice Reconciliation Platform

AI-powered web platform for automated contract and invoice reconciliation using OCR and GPT.

## Features

- **OCR Processing**: Extracts text from PDF and image files using Tesseract
- **AI Analysis**: Uses GPT to understand and extract key terms from documents
- **Automated Reconciliation**: Compares contracts against invoices to find discrepancies
- **User-Friendly Dashboard**: Simple interface for uploading files and viewing results
- **Detailed Reporting**: Highlights mismatches, warnings, and matching fields

## Prerequisites

- Python 3.8+
- Tesseract OCR installed on your system
- OpenAI API key

### Installing Tesseract

**macOS:**
```bash
brew install tesseract
```

**Ubuntu/Debian:**
```bash
sudo apt-get install tesseract-ocr
```

**Windows:**
Download installer from: https://github.com/UB-Mannheim/tesseract/wiki

## Installation

1. Clone the repository and navigate to the project directory:
```bash
cd invoice-reconciliation-platform
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example`:
```bash
cp .env.example .env
```

4. Add your OpenAI API key to the `.env` file:
```
OPENAI_API_KEY=your_actual_api_key_here
```

## Running the Application

1. Start the Flask backend server:
```bash
cd backend
python app.py
```

2. Open your browser and navigate to:
```
http://localhost:5000
```

## Usage

1. **Upload Documents**: Select both a contract PDF/image and an invoice PDF/image
2. **Start Reconciliation**: Click the "Start Reconciliation" button
3. **View Results**: The system will:
   - Extract text using OCR
   - Analyze documents with AI
   - Compare and highlight discrepancies
   - Display a comprehensive reconciliation report

## Project Structure

```
invoice-reconciliation-platform/
├── backend/
│   ├── app.py              # Flask API server
│   ├── ocr_processor.py    # OCR text extraction
│   └── ai_analyzer.py      # AI-powered analysis
├── frontend/
│   ├── index.html          # Main dashboard
│   ├── styles.css          # Styling
│   └── app.js              # Frontend logic
├── uploads/                # Temporary file storage
├── processed/              # Processed documents
├── requirements.txt        # Python dependencies
├── .env.example           # Environment variables template
└── README.md              # Documentation
```

## API Endpoints

- `POST /api/upload` - Upload contract and invoice files
- `POST /api/process/<session_id>` - Process uploaded documents
- `GET /api/results/<session_id>` - Get reconciliation results
- `GET /api/sessions` - List all reconciliation sessions
- `GET /api/health` - Health check endpoint

## Technologies Used

- **Backend**: Python, Flask, Flask-CORS
- **OCR**: Tesseract, PyTesseract, pdf2image
- **AI**: OpenAI GPT-3.5-turbo
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **Libraries**: Pillow, NumPy, Pandas

## Troubleshooting

### Tesseract not found
Ensure Tesseract is installed and in your system PATH. You may need to specify the path:
```python
pytesseract.pytesseract.tesseract_cmd = r'/usr/local/bin/tesseract'
```

### PDF processing issues
Install poppler-utils for PDF to image conversion:
- macOS: `brew install poppler`
- Ubuntu: `sudo apt-get install poppler-utils`

### CORS errors
Ensure the Flask backend is running on port 5000 and CORS is properly configured.

## Security Notes

- Never commit your `.env` file with actual API keys
- Use environment variables for sensitive configuration
- Implement proper authentication for production use
- Add file size and type validation for production