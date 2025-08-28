@echo off
REM Outre Couture Backend Startup Script for Windows

echo ==========================================
echo Outre Couture Backend Startup
echo ==========================================

REM Check if virtual environment exists
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

REM Check if .env file exists
if not exist ".env" (
    echo Creating .env file from template...
    copy env.example .env
    echo Please edit .env file with your configuration before running the app.
    echo Required settings:
    echo   - MONGO_URI: MongoDB connection string (updated to use outre_couture database)
    echo   - MAIL_USERNAME: Your email address
    echo   - MAIL_PASSWORD: Your email password/app password
    echo   - ADMIN_EMAIL: Admin email for RFQ notifications
    echo.
    echo Note: The MongoDB URI has been updated to use the outre_couture database.
    echo The database will be created automatically when the app starts.
    pause
    exit /b 1
)

REM Initialize database with sample data
echo Initializing database with sample data...
python init_db.py

REM Start the Flask application
echo Starting Flask application...
echo API will be available at: http://localhost:5000
echo Press Ctrl+C to stop the server
echo ==========================================

python app.py
