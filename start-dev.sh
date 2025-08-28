#!/bin/bash

# Development Environment Startup Script

echo "=========================================="
echo "Outre Couture Backend - Development Mode"
echo "=========================================="

# Set environment
export FLASK_ENV=development

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

# Check if env.development file exists
if [ ! -f "env.development" ]; then
    echo "Creating env.development file..."
    cp env.example env.development
    echo "Please edit env.development file with your configuration."
    echo "Required settings:"
    echo "  - MONGO_URI: MongoDB connection string (updated to use outre_couture database)"
    echo "  - MAIL_USERNAME: Your email address"
    echo "  - MAIL_PASSWORD: Your email password/app password"
    echo "  - ADMIN_EMAIL: Admin email for RFQ notifications"
    echo ""
    echo "Note: The MongoDB URI has been updated to use the outre_couture database."
    echo "The database will be created automatically when the app starts."
    exit 1
fi

# Initialize database with sample data
echo "Initializing database with sample data..."
python3 init_db.py

# Start the Flask application
echo "Starting Flask application in development mode..."
echo "API will be available at: http://localhost:5000/api"
echo "Press Ctrl+C to stop the server"
echo "=========================================="

python3 app.py
