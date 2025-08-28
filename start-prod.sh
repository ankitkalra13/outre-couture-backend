#!/bin/bash

# Production Environment Startup Script

echo "=========================================="
echo "Outre Couture Backend - Production Mode"
echo "=========================================="

# Set environment
export FLASK_ENV=production

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Install Gunicorn for production
echo "Installing Gunicorn for production..."
pip install gunicorn

# Check if env.production file exists
if [ ! -f "env.production" ]; then
    echo "Error: env.production file not found!"
    echo "Please create env.production file with production configuration."
    echo "You can copy from env.example and modify for production:"
    echo "  cp env.example env.production"
    echo ""
    echo "Note: The MongoDB URI has been updated to use the outre_couture database."
    echo "The database will be created automatically when the app starts."
    exit 1
fi

# Start the Flask application with production server
echo "Starting Flask application in production mode..."
echo "API will be available at: https://api.outrecouture.com/api"
echo "Press Ctrl+C to stop the server"
echo "=========================================="

# Use Gunicorn for production
gunicorn -w 4 -b 0.0.0.0:5000 app:app
