# Environment-Based Setup Guide

This guide explains how to set up and use different environments (development, staging, production) for the Outre Couture Backend API.

## 🏗️ **Environment Configuration Files**

The project now supports three different environments:

### **Development Environment** (`env.development`)
- **Base URL**: `http://localhost:5000/api`
- **Database**: Local MongoDB
- **Debug**: Enabled
- **Use Case**: Local development and testing

### **Staging Environment** (`env.staging`)
- **Base URL**: `https://staging-api.outrecouture.com/api`
- **Database**: Staging MongoDB
- **Debug**: Disabled
- **Use Case**: Pre-production testing

### **Production Environment** (`env.production`)
- **Base URL**: `https://api.outrecouture.com/api`
- **Database**: Production MongoDB
- **Debug**: Disabled
- **Use Case**: Live production system

## 🚀 **Quick Start**

### **1. Development Setup**

```bash
# Linux/Mac
./start-dev.sh

# Windows
start-dev.bat
```

### **2. Staging Setup**

```bash
# Linux/Mac
./start-staging.sh

# Windows
# Create start-staging.bat similar to start-dev.bat
```

### **3. Production Setup**

```bash
# Linux/Mac
./start-prod.sh

# Windows
# Create start-prod.bat similar to start-dev.bat
```

## ⚙️ **Manual Environment Setup**

### **Step 1: Create Environment Files**

Copy the example environment file for each environment:

```bash
# Development
cp env.example env.development

# Staging
cp env.example env.staging

# Production
cp env.example env.production
```

### **Step 2: Configure Each Environment**

Edit each environment file with appropriate settings:

#### **Development** (`env.development`)
```bash
FLASK_ENV=development
FLASK_DEBUG=True
BASE_URL=http://localhost:5000/api
MONGO_URI=mongodb://localhost:27017/
JWT_SECRET_KEY=dev-secret-key-change-in-production
```

#### **Staging** (`env.staging`)
```bash
FLASK_ENV=staging
FLASK_DEBUG=False
BASE_URL=https://staging-api.outrecouture.com/api
MONGO_URI=mongodb://staging-mongo:27017/
JWT_SECRET_KEY=staging-super-secret-jwt-key
```

#### **Production** (`env.production`)
```bash
FLASK_ENV=production
FLASK_DEBUG=False
BASE_URL=https://api.outrecouture.com/api
MONGO_URI=mongodb://production-mongo:27017/
JWT_SECRET_KEY=production-super-secret-jwt-key-change-this
```

### **Step 3: Set Environment Variable and Run**

```bash
# Development
export FLASK_ENV=development
python app.py

# Staging
export FLASK_ENV=staging
python app.py

# Production
export FLASK_ENV=production
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

## 🧪 **Testing Different Environments**

### **Test Development Environment**
```bash
export FLASK_ENV=development
python test_api.py
```

### **Test Staging Environment**
```bash
export FLASK_ENV=staging
python test_api.py
```

### **Test Production Environment**
```bash
export FLASK_ENV=production
python test_api.py
```

## 🔍 **Environment Detection**

The application automatically detects the environment and loads the appropriate configuration:

1. **Checks** `FLASK_ENV` environment variable
2. **Loads** `env.{environment}` file (e.g., `env.development`)
3. **Falls back** to `.env` if environment file doesn't exist
4. **Displays** loaded configuration on startup

### **Health Check Response**
The health check endpoint now includes environment information:

```json
{
  "success": true,
  "status": "healthy",
  "environment": "development",
  "base_url": "http://localhost:5000/api",
  "database": "connected",
  "timestamp": "2024-01-01T00:00:00.000Z"
}
```

## 🔧 **Configuration Variables**

### **API Configuration**
- `BASE_URL`: The base URL for the API
- `API_HOST`: Host to bind the server to
- `API_PORT`: Port to run the server on

### **Database Configuration**
- `MONGO_URI`: MongoDB connection string

### **Email Configuration**
- `MAIL_SERVER`: SMTP server
- `MAIL_PORT`: SMTP port
- `MAIL_USERNAME`: Email username
- `MAIL_PASSWORD`: Email password
- `MAIL_DEFAULT_SENDER`: Default sender email

### **JWT Configuration**
- `JWT_SECRET_KEY`: Secret key for JWT tokens
- `JWT_EXPIRATION_HOURS`: Access token expiration time
- `JWT_REFRESH_EXPIRATION_DAYS`: Refresh token expiration time

### **Security Configuration**
- `BCRYPT_ROUNDS`: Password hashing rounds
- `PASSWORD_MIN_LENGTH`: Minimum password length
- `MAX_LOGIN_ATTEMPTS`: Maximum failed login attempts
- `LOGIN_LOCKOUT_MINUTES`: Account lockout duration

## 🛡️ **Security Best Practices**

### **Environment-Specific Secrets**
- Use **different JWT secrets** for each environment
- Use **different database credentials** for each environment
- Use **different email accounts** for each environment

### **Production Security**
- **Never commit** `env.production` to version control
- Use **HTTPS** in staging and production
- Use **strong passwords** and secrets
- Enable **debug mode** only in development

### **File Permissions**
```bash
# Make environment files readable only by owner
chmod 600 env.production
chmod 600 env.staging
chmod 600 env.development
```

## 🔄 **Environment Switching**

### **Quick Environment Switch**
```bash
# Switch to development
export FLASK_ENV=development
python app.py

# Switch to staging
export FLASK_ENV=staging
python app.py

# Switch to production
export FLASK_ENV=production
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### **Permanent Environment Setting**
Add to your shell profile (`~/.bashrc`, `~/.zshrc`):
```bash
# For development
export FLASK_ENV=development

# For staging
export FLASK_ENV=staging

# For production
export FLASK_ENV=production
```

## 📊 **Environment Comparison**

| Feature | Development | Staging | Production |
|---------|-------------|---------|------------|
| **Base URL** | `http://localhost:5000/api` | `https://staging-api.outrecouture.com/api` | `https://api.outrecouture.com/api` |
| **Debug Mode** | ✅ Enabled | ❌ Disabled | ❌ Disabled |
| **Database** | Local MongoDB | Staging MongoDB | Production MongoDB |
| **Email** | Development account | Staging account | Production account |
| **JWT Secret** | Dev secret | Staging secret | Production secret |
| **Server** | Flask dev server | Flask dev server | Gunicorn |

## 🚨 **Troubleshooting**

### **Environment File Not Found**
```
Error: env.production file not found!
```
**Solution**: Create the environment file:
```bash
cp env.example env.production
# Edit env.production with production settings
```

### **Wrong Environment Loaded**
**Check**: Look at the startup message:
```
Loaded environment configuration from: env.development
```

**Solution**: Set the correct environment:
```bash
export FLASK_ENV=production
```

### **Base URL Mismatch**
**Check**: Health check response shows current base URL
**Solution**: Update the `BASE_URL` in your environment file

## 📝 **Example Usage**

### **Complete Development Workflow**
```bash
# 1. Set environment
export FLASK_ENV=development

# 2. Start application
python app.py

# 3. Test API
python test_api.py

# 4. Check health
curl http://localhost:5000/api/health
```

### **Complete Production Deployment**
```bash
# 1. Set environment
export FLASK_ENV=production

# 2. Install production dependencies
pip install gunicorn

# 3. Start with Gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app

# 4. Test production API
python test_api.py
```

This environment-based setup provides complete flexibility for running your Outre Couture backend in different environments with appropriate configurations! 🎉
