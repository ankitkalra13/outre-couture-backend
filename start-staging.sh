#!/bin/bash

# Staging Environment Startup Script

echo "=========================================="
echo "Outre Couture Backend - Staging Mode"
echo "=========================================="

# Set environment
export FLASK_ENV=staging

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

# Check if env.staging file exists
if [ ! -f "env.staging" ]; then
    echo "Error: env.staging file not found!"
    echo "Please create env.staging file with staging configuration."
    echo "You can copy from env.example and modify for staging:"
    echo "  cp env.example env.staging"
    echo ""
    echo "Note: The MongoDB URI has been updated to use the outre_couture database."
    echo "The database will be created automatically when the app starts."
    exit 1
fi

# Start the Flask application
echo "Starting Flask application in staging mode..."
echo "API will be available at: https://staging-api.outrecouture.com/api"
echo "Press Ctrl+C to stop the server"
echo "=========================================="

python app.py
