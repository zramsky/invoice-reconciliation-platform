#!/bin/bash

# Invoice Reconciliation Platform Backend Startup Script

echo "🚀 Starting Invoice Reconciliation Platform Backend..."

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "📚 Installing requirements..."
pip install -r requirements.txt

# Create necessary directories
echo "📁 Creating upload directories..."
mkdir -p uploads/vendors
mkdir -p processed

# Set environment variables if .env doesn't exist
if [ ! -f ".env" ]; then
    echo "⚙️ Creating .env file..."
    cat > .env << EOL
UPLOAD_FOLDER=uploads
PROCESSED_FOLDER=processed
MAX_FILE_SIZE=10485760
OPENAI_API_KEY=your_openai_api_key_here
EOL
    echo "📝 Please edit .env file and add your OpenAI API key"
fi

# Start the Flask backend
echo "🌐 Starting Flask backend on http://localhost:5000..."
cd backend
python app.py