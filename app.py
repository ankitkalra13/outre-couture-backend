"""
Outre Couture Backend API

A Flask-based REST API for Outre Couture's admin panel and website.
Provides product management, category management, and RFQ handling with email notifications.
"""

import json
import os
import uuid
import secrets
from datetime import datetime, timedelta

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_mail import Mail, Message
from pymongo import MongoClient
from bson import ObjectId
from dotenv import load_dotenv
import jwt
import bcrypt

# Load environment-specific configuration
ENV = os.getenv('FLASK_ENV', 'development')
env_file = f'env.{ENV}'

if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"Loaded environment configuration from: {env_file}")
else:
    load_dotenv()  # Fallback to .env
    print(f"Loaded default environment configuration")

# Get API configuration from environment
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000/api')
API_HOST = os.getenv('API_HOST', '0.0.0.0')
API_PORT = int(os.getenv('API_PORT', 5000))

app = Flask(__name__)
# CORS Configuration - Allow both development and production domains
CORS(app, origins=[
    'http://localhost:3000', 
    'http://localhost:3001',
    'https://outre-couture.vercel.app',  # Your Vercel domain
    'https://outre-couture-frontend.vercel.app'  # Alternative Vercel domain
], supports_credentials=True)

# MongoDB Configuration
MONGO_URI = os.getenv('MONGO_URI', 'mongodb+srv://ankitkalra13:0yQ4N2JY1hJVXmyT@cluster0.j2yojqe.mongodb.net')
client = MongoClient(MONGO_URI)
db = client['outre_couture']

# Collections
products_collection = db['products']
categories_collection = db['categories']
rfq_collection = db['rfq_requests']

# Email Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)

# JWT Configuration
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', secrets.token_urlsafe(32))
app.config['JWT_ALGORITHM'] = 'HS256'
app.config['JWT_EXPIRATION_HOURS'] = int(os.getenv('JWT_EXPIRATION_HOURS', 24))
app.config['JWT_REFRESH_EXPIRATION_DAYS'] = int(os.getenv('JWT_REFRESH_EXPIRATION_DAYS', 7))

# Security Configuration
app.config['BCRYPT_ROUNDS'] = int(os.getenv('BCRYPT_ROUNDS', 12))
app.config['PASSWORD_MIN_LENGTH'] = int(os.getenv('PASSWORD_MIN_LENGTH', 8))
app.config['MAX_LOGIN_ATTEMPTS'] = int(os.getenv('MAX_LOGIN_ATTEMPTS', 5))
app.config['LOGIN_LOCKOUT_MINUTES'] = int(os.getenv('LOGIN_LOCKOUT_MINUTES', 15))

# Collections
users_collection = db['users']

# In-memory storage for login attempts (in production, use Redis)
login_attempts = {}
account_lockouts = {}

# Helper function to send emails
def send_email(to_email, subject, body):
    """Send an email using Flask-Mail.
    
    Args:
        to_email (str): Recipient email address
        subject (str): Email subject
        body (str): Email body content
        
    Returns:
        bool: True if email sent successfully, False otherwise
    """
    try:
        msg = Message(subject, recipients=[to_email])
        msg.body = body
        mail.send(msg)
        return True
    except (ConnectionError, ValueError, TypeError) as e:
        print(f"Email sending failed: {e}")
        return False

# Helper function to validate ObjectId
def is_valid_object_id(id_string):
    try:
        ObjectId(id_string)
        return True
    except (ValueError, TypeError):
        return False

# JWT Helper Functions
def generate_token(user_id, username, role='user'):
    """Generate JWT token for user authentication"""
    payload = {
        'user_id': str(user_id),
        'username': username,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=app.config['JWT_EXPIRATION_HOURS']),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm=app.config['JWT_ALGORITHM'])

def verify_token(token):
    """Verify JWT token and return payload if valid"""
    try:
        payload = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=[app.config['JWT_ALGORITHM']])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_auth(f):
    """Decorator to require authentication for protected routes"""
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Authorization header required'}), 401
        
        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        if not payload:
            return jsonify({'success': False, 'error': 'Invalid or expired token'}), 401
        
        request.user = payload
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

def require_admin(f):
    """Decorator to require admin role for protected routes"""
    def decorated_function(*args, **kwargs):
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Authorization header required'}), 401
        
        token = auth_header.split(' ')[1]
        payload = verify_token(token)
        if not payload:
            return jsonify({'success': False, 'error': 'Invalid or expired token'}), 401
        
        if payload.get('role') != 'admin':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        
        request.user = payload
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Security Helper Functions
def hash_password(password):
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt(rounds=app.config['BCRYPT_ROUNDS'])
    return bcrypt.hashpw(password.encode('utf-8'), salt)

def verify_password(password, hashed_password):
    """Verify password against hashed password"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password)

def validate_password(password):
    """Validate password strength"""
    if len(password) < app.config['PASSWORD_MIN_LENGTH']:
        return False, f"Password must be at least {app.config['PASSWORD_MIN_LENGTH']} characters long"
    
    # Check for at least one uppercase, one lowercase, one digit
    if not any(c.isupper() for c in password):
        return False, "Password must contain at least one uppercase letter"
    if not any(c.islower() for c in password):
        return False, "Password must contain at least one lowercase letter"
    if not any(c.isdigit() for c in password):
        return False, "Password must contain at least one digit"
    
    return True, "Password is valid"

def validate_email(email):
    """Basic email validation"""
    import re
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def check_login_attempts(username):
    """Check if user is locked out due to too many failed login attempts"""
    # Check if user is locked out
    if username in account_lockouts:
        lockout_time = account_lockouts[username]
        if datetime.utcnow() < lockout_time:
            remaining_minutes = int((lockout_time - datetime.utcnow()).total_seconds() / 60)
            return False, f"Account temporarily locked. Try again in {remaining_minutes} minutes"
        else:
            # Remove expired lockout
            del account_lockouts[username]
    
    return True, None

def record_failed_login(username):
    """Record a failed login attempt"""
    # Increment failed attempts
    failed_attempts = login_attempts.get(username, 0) + 1
    login_attempts[username] = failed_attempts
    
    # Lock account if max attempts reached
    if failed_attempts >= app.config['MAX_LOGIN_ATTEMPTS']:
        lockout_time = datetime.utcnow() + timedelta(minutes=app.config['LOGIN_LOCKOUT_MINUTES'])
        account_lockouts[username] = lockout_time
        return f"Account locked for {app.config['LOGIN_LOCKOUT_MINUTES']} minutes due to too many failed attempts"
    
    return None

def clear_failed_attempts(username):
    """Clear failed login attempts after successful login"""
    if username in login_attempts:
        del login_attempts[username]
    if username in account_lockouts:
        del account_lockouts[username]

def generate_refresh_token(user_id, username, role='user'):
    """Generate refresh token for token renewal"""
    payload = {
        'user_id': str(user_id),
        'username': username,
        'role': role,
        'type': 'refresh',
        'exp': datetime.utcnow() + timedelta(days=app.config['JWT_REFRESH_EXPIRATION_DAYS']),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, app.config['JWT_SECRET_KEY'], algorithm=app.config['JWT_ALGORITHM'])

def sanitize_input(data):
    """Sanitize user input to prevent injection attacks"""
    if isinstance(data, str):
        # Remove potentially dangerous characters
        return data.strip().replace('<', '&lt;').replace('>', '&gt;')
    elif isinstance(data, dict):
        return {k: sanitize_input(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
    return data

def convert_to_json_serializable(obj):
    """Convert MongoDB objects to JSON serializable format"""
    if isinstance(obj, dict):
        return {k: convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(item) for item in obj]
    elif isinstance(obj, ObjectId):
        return str(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj

# ==================== AUTHENTICATION APIs ====================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        if not data or 'username' not in data or 'password' not in data or 'email' not in data:
            return jsonify({'success': False, 'error': 'Username, password, and email are required'}), 400
        
        # Sanitize input
        data = sanitize_input(data)
        
        # Validate email
        if not validate_email(data['email']):
            return jsonify({'success': False, 'error': 'Invalid email format'}), 400
        
        # Validate password strength
        is_valid, password_error = validate_password(data['password'])
        if not is_valid:
            return jsonify({'success': False, 'error': password_error}), 400
        
        # Check if user already exists
        existing_user = users_collection.find_one({'$or': [{'username': data['username']}, {'email': data['email']}]})
        if existing_user:
            return jsonify({'success': False, 'error': 'Username or email already exists'}), 400
        
        # Hash password
        hashed_password = hash_password(data['password'])
        
        # Create new user
        user = {
            'username': data['username'],
            'password': hashed_password,
            'email': data['email'],
            'role': data.get('role', 'user'),
            'created_at': datetime.utcnow(),
            'last_login': None,
            'is_active': True
        }
        
        result = users_collection.insert_one(user)
        user['_id'] = str(result.inserted_id)
        del user['password']  # Don't return password
        
        # Generate tokens
        access_token = generate_token(result.inserted_id, data['username'], user['role'])
        refresh_token = generate_refresh_token(result.inserted_id, data['username'], user['role'])
        
        return jsonify({
            'success': True, 
            'message': 'User registered successfully',
            'user': user,
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 201
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login user and return JWT token"""
    try:
        data = request.get_json()
        
        if not data or 'username' not in data or 'password' not in data:
            return jsonify({'success': False, 'error': 'Username and password are required'}), 400
        
        # Sanitize input
        data = sanitize_input(data)
        
        # Check for account lockout
        can_login, lockout_message = check_login_attempts(data['username'])
        if not can_login:
            return jsonify({'success': False, 'error': lockout_message}), 423  # 423 Locked
        
        # Find user
        user = users_collection.find_one({'username': data['username']})
        if not user:
            record_failed_login(data['username'])
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        # Check if account is active
        if not user.get('is_active', True):
            return jsonify({'success': False, 'error': 'Account is deactivated'}), 401
        
        # Verify password
        if not verify_password(data['password'], user['password']):
            record_failed_login(data['username'])
            return jsonify({'success': False, 'error': 'Invalid credentials'}), 401
        
        # Clear failed attempts on successful login
        clear_failed_attempts(data['username'])
        
        # Update last login
        users_collection.update_one(
            {'_id': user['_id']},
            {'$set': {'last_login': datetime.utcnow()}}
        )
        
        # Generate tokens
        access_token = generate_token(user['_id'], user['username'], user.get('role', 'user'))
        refresh_token = generate_refresh_token(user['_id'], user['username'], user.get('role', 'user'))
        
        # Return user info without password
        user_info = {
            '_id': str(user['_id']),
            'username': user['username'],
            'email': user['email'],
            'role': user.get('role', 'user'),
            'last_login': user.get('last_login')
        }
        
        return jsonify({
            'success': True,
            'message': 'Login successful',
            'user': user_info,
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/verify', methods=['GET'])
@require_auth
def verify_token_route():
    """Verify JWT token and return user info"""
    return jsonify({
        'success': True,
        'user': request.user
    }), 200

@app.route('/api/auth/refresh', methods=['POST'])
def refresh_token():
    """Refresh access token using refresh token"""
    try:
        data = request.get_json()
        
        if not data or 'refresh_token' not in data:
            return jsonify({'success': False, 'error': 'Refresh token is required'}), 400
        
        # Verify refresh token
        try:
            payload = jwt.decode(data['refresh_token'], app.config['JWT_SECRET_KEY'], algorithms=[app.config['JWT_ALGORITHM']])
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'error': 'Refresh token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'error': 'Invalid refresh token'}), 401
        
        # Check if it's a refresh token
        if payload.get('type') != 'refresh':
            return jsonify({'success': False, 'error': 'Invalid token type'}), 401
        
        # Get user from database
        user = users_collection.find_one({'_id': ObjectId(payload['user_id'])})
        if not user or not user.get('is_active', True):
            return jsonify({'success': False, 'error': 'User not found or inactive'}), 401
        
        # Generate new tokens
        access_token = generate_token(user['_id'], user['username'], user.get('role', 'user'))
        refresh_token = generate_refresh_token(user['_id'], user['username'], user.get('role', 'user'))
        
        return jsonify({
            'success': True,
            'message': 'Token refreshed successfully',
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/auth/logout', methods=['POST'])
@require_auth
def logout():
    """Logout user (client should discard tokens)"""
    # In a more advanced implementation, you might want to blacklist the token
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    }), 200

# ==================== CATEGORY APIs ====================

@app.route('/api/categories', methods=['GET'])
def get_categories():
    """Get all categories"""
    try:
        categories = list(categories_collection.find({}, {'_id': 0}))
        # Convert to JSON serializable format
        categories_json = convert_to_json_serializable(categories)
        return jsonify({'success': True, 'categories': categories_json}), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories/main', methods=['GET'])
def get_main_categories():
    """Get main categories only"""
    try:
        main_categories = list(categories_collection.find({'type': 'main'}, {'_id': 0}))
        # Convert to JSON serializable format
        categories_json = convert_to_json_serializable(main_categories)
        return jsonify({'success': True, 'categories': categories_json}), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories/sub/<main_category_slug>', methods=['GET'])
def get_sub_categories(main_category_slug):
    """Get sub-categories for a specific main category"""
    try:
        # First find the main category
        main_category = categories_collection.find_one({'slug': main_category_slug, 'type': 'main'})
        if not main_category:
            return jsonify({'success': False, 'error': 'Main category not found'}), 404
        
        # Get sub-categories for this main category
        sub_categories = list(categories_collection.find(
            {'main_category_id': main_category['id'], 'type': 'sub'}, 
            {'_id': 0}
        ))
        
        # Convert to JSON serializable format
        categories_json = convert_to_json_serializable(sub_categories)
        return jsonify({'success': True, 'categories': categories_json}), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories', methods=['POST'])
@require_admin
def create_category():
    """Create a new category (main or sub-category)"""
    try:
        data = request.get_json()
        
        if not data or 'name' not in data or 'type' not in data:
            return jsonify({'success': False, 'error': 'Category name and type are required'}), 400
        
        # Sanitize input
        data = sanitize_input(data)
        
        # Validate category type
        if data['type'] not in ['main', 'sub']:
            return jsonify({'success': False, 'error': 'Category type must be either "main" or "sub"'}), 400
        
        # Validate category name
        if len(data['name'].strip()) < 2:
            return jsonify({'success': False, 'error': 'Category name must be at least 2 characters long'}), 400
        
        # For sub-categories, validate main category
        if data['type'] == 'sub':
            if 'main_category_id' not in data:
                return jsonify({'success': False, 'error': 'main_category_id is required for sub-categories'}), 400
            
            # Check if main category exists
            main_category = categories_collection.find_one({'id': data['main_category_id'], 'type': 'main'})
            if not main_category:
                return jsonify({'success': False, 'error': 'Invalid main_category_id'}), 400
        
        # Check if category already exists (considering type and main category)
        query = {'name': data['name'], 'type': data['type']}
        if data['type'] == 'sub':
            query['main_category_id'] = data['main_category_id']
        
        existing_category = categories_collection.find_one(query)
        if existing_category:
            return jsonify({'success': False, 'error': 'Category already exists'}), 400
        
        # Create category object
        category = {
            'id': str(uuid.uuid4()),
            'name': data['name'].strip(),
            'type': data['type'],
            'description': data.get('description', '').strip(),
            'slug': data.get('slug', data['name'].lower().replace(' ', '-').replace('&', 'and')),
            'created_at': datetime.utcnow().isoformat(),
            'created_by': str(request.user['user_id'])
        }
        
        # Add sub-category specific fields
        if data['type'] == 'sub':
            category.update({
                'main_category_id': data['main_category_id'],
                'main_category_name': main_category['name'],
                'main_category_slug': main_category['slug']
            })
        
        categories_collection.insert_one(category)
        # Convert to JSON serializable format
        category_json = convert_to_json_serializable(category)
        return jsonify({'success': True, 'category': category_json}), 201
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories/admin', methods=['GET'])
@require_admin
def get_categories_for_admin():
    """Get all categories organized by type for admin panel"""
    try:
        # Get main categories
        main_categories = list(categories_collection.find(
            {'type': 'main'}, 
            {'_id': 0}
        ).sort('name', 1))
        
        # Get sub-categories grouped by main category
        sub_categories_by_main = {}
        for main_cat in main_categories:
            sub_cats = list(categories_collection.find(
                {'main_category_id': main_cat['id'], 'type': 'sub'}, 
                {'_id': 0}
            ).sort('name', 1))
            sub_categories_by_main[main_cat['id']] = sub_cats
        
        # Convert to JSON serializable format
        main_categories_json = convert_to_json_serializable(main_categories)
        sub_categories_by_main_json = convert_to_json_serializable(sub_categories_by_main)
        
        return jsonify({
            'success': True, 
            'main_categories': main_categories_json,
            'sub_categories_by_main': sub_categories_by_main_json
        }), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories/<category_id>', methods=['PUT'])
@require_admin
def update_category(category_id):
    """Update a category (Admin only)"""
    try:
        data = request.get_json()
        
        # Check if category exists
        existing_category = categories_collection.find_one({'id': category_id})
        if not existing_category:
            return jsonify({'success': False, 'error': 'Category not found'}), 404
        
        # Sanitize input
        data = sanitize_input(data)
        
        # Update fields
        update_data = {
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if 'name' in data:
            if len(data['name'].strip()) < 2:
                return jsonify({'success': False, 'error': 'Category name must be at least 2 characters long'}), 400
            
            # Check if new name conflicts with existing category
            if data['name'].strip() != existing_category['name']:
                conflict_category = categories_collection.find_one({'name': data['name'].strip()})
                if conflict_category:
                    return jsonify({'success': False, 'error': 'Category name already exists'}), 400
            
            update_data['name'] = data['name'].strip()
        
        if 'description' in data:
            update_data['description'] = data['description'].strip()
        
        categories_collection.update_one(
            {'id': category_id},
            {'$set': update_data}
        )
        
        # Get updated category
        updated_category = categories_collection.find_one({'id': category_id}, {'_id': 0})
        # Convert to JSON serializable format
        updated_category_json = convert_to_json_serializable(updated_category)
        return jsonify({'success': True, 'category': updated_category_json}), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/categories/<category_id>', methods=['DELETE'])
@require_admin
def delete_category(category_id):
    """Delete a category (Admin only)"""
    try:
        # Check if category exists
        existing_category = categories_collection.find_one({'id': category_id})
        if not existing_category:
            return jsonify({'success': False, 'error': 'Category not found'}), 404
        
        # Check if category is used by any products
        products_using_category = products_collection.count_documents({'category_id': category_id})
        if products_using_category > 0:
            return jsonify({
                'success': False, 
                'error': f'Cannot delete category. {products_using_category} product(s) are using this category.'
            }), 400
        
        result = categories_collection.delete_one({'id': category_id})
        if result.deleted_count == 0:
            return jsonify({'success': False, 'error': 'Category not found'}), 404
        
        return jsonify({'success': True, 'message': 'Category deleted successfully'}), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== PRODUCT APIs ====================

@app.route('/api/products', methods=['POST'])
@require_admin
def create_product():
    """Create a new product (Admin only)"""
    try:
        data = request.get_json()
        
        required_fields = ['name', 'category_id', 'description']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        
        # Sanitize input
        data = sanitize_input(data)
        
        # Validate product name
        if len(data['name'].strip()) < 3:
            return jsonify({'success': False, 'error': 'Product name must be at least 3 characters long'}), 400
        
        # Validate sub-category exists and get main category info
        sub_category = categories_collection.find_one({'id': data['category_id'], 'type': 'sub'})
        if not sub_category:
            return jsonify({'success': False, 'error': 'Invalid category_id - must be a sub-category'}), 400
        
        # Get main category info
        main_category = categories_collection.find_one({'id': sub_category['main_category_id'], 'type': 'main'})
        if not main_category:
            return jsonify({'success': False, 'error': 'Invalid main category reference'}), 400
        
        # Validate images array
        images = data.get('images', [])
        if not isinstance(images, list):
            return jsonify({'success': False, 'error': 'Images must be an array'}), 400
        
        product = {
            'id': str(uuid.uuid4()),
            'name': data['name'].strip(),
            'category_id': data['category_id'],
            'category_name': sub_category['name'],
            'main_category_name': main_category['name'],
            'main_category_slug': main_category['slug'],
            'description': data['description'].strip(),
            'images': images,
            'specifications': data.get('specifications', {}),
            'is_active': data.get('is_active', True),
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat(),
            'created_by': str(request.user['user_id'])
        }
        
        products_collection.insert_one(product)
        # Convert to JSON serializable format
        product_json = convert_to_json_serializable(product)
        return jsonify({'success': True, 'product': product_json}), 201
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/products', methods=['GET'])
def get_products():
    """Get all products (with optional filters)"""
    try:
        # Query parameters
        category_id = request.args.get('category_id')
        is_active = request.args.get('is_active', 'true').lower() == 'true'
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))
        
        # Build query
        query = {'is_active': is_active}
        if category_id:
            query['category_id'] = category_id
        
        products = list(products_collection.find(query, {'_id': 0}).skip(skip).limit(limit))
        
        # Convert to JSON serializable format
        products_json = convert_to_json_serializable(products)
        
        return jsonify({
            'success': True, 
            'products': products_json,
            'total': len(products),
            'limit': limit,
            'skip': skip
        }), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/products/<product_id>', methods=['GET'])
def get_product(product_id):
    """Get a specific product by ID"""
    try:
        product = products_collection.find_one({'id': product_id}, {'_id': 0})
        if not product:
            return jsonify({'success': False, 'error': 'Product not found'}), 404
        
        # Convert to JSON serializable format
        product_json = convert_to_json_serializable(product)
        return jsonify({'success': True, 'product': product_json}), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/products/category/<main_category_slug>', methods=['GET'])
def get_products_by_main_category(main_category_slug):
    """Get products by main category slug"""
    try:
        # Query parameters
        sub_category_id = request.args.get('sub_category_id')
        is_active = request.args.get('is_active', 'true').lower() == 'true'
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))
        
        # Build query
        query = {'is_active': is_active, 'main_category_slug': main_category_slug}
        if sub_category_id:
            query['category_id'] = sub_category_id
        
        products = list(products_collection.find(query, {'_id': 0}).skip(skip).limit(limit))
        
        # Convert to JSON serializable format
        products_json = convert_to_json_serializable(products)
        
        return jsonify({
            'success': True, 
            'products': products_json,
            'total': len(products),
            'limit': limit,
            'skip': skip
        }), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/products/<product_id>', methods=['PUT'])
@require_admin
def update_product(product_id):
    """Update a product (Admin only)"""
    try:
        data = request.get_json()
        
        # Check if product exists
        existing_product = products_collection.find_one({'id': product_id})
        if not existing_product:
            return jsonify({'success': False, 'error': 'Product not found'}), 404
        
        # Update fields
        update_data = {
            'updated_at': datetime.utcnow().isoformat()
        }
        
        if 'name' in data:
            update_data['name'] = data['name']
        if 'category_id' in data:
            # Validate category exists
            category = categories_collection.find_one({'id': data['category_id']})
            if not category:
                return jsonify({'success': False, 'error': 'Invalid category_id'}), 400
            update_data['category_id'] = data['category_id']
            update_data['category_name'] = category['name']

        if 'description' in data:
            update_data['description'] = data['description']
        if 'images' in data:
            update_data['images'] = data['images']
        if 'specifications' in data:
            update_data['specifications'] = data['specifications']
        if 'is_active' in data:
            update_data['is_active'] = data['is_active']
        
        products_collection.update_one(
            {'id': product_id},
            {'$set': update_data}
        )
        
        # Get updated product
        updated_product = products_collection.find_one({'id': product_id}, {'_id': 0})
        # Convert to JSON serializable format
        updated_product_json = convert_to_json_serializable(updated_product)
        return jsonify({'success': True, 'product': updated_product_json}), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/products/<product_id>', methods=['DELETE'])
@require_admin
def delete_product(product_id):
    """Delete a product (Admin only)"""
    try:
        result = products_collection.delete_one({'id': product_id})
        if result.deleted_count == 0:
            return jsonify({'success': False, 'error': 'Product not found'}), 404
        
        return jsonify({'success': True, 'message': 'Product deleted successfully'}), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== RFQ APIs ====================

@app.route('/api/rfq', methods=['POST'])
def submit_rfq():
    """Submit RFQ form and send emails"""
    try:
        data = request.get_json()
        
        required_fields = ['name', 'email', 'phone', 'company', 'requirements']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'{field} is required'}), 400
        
        # Create RFQ record
        rfq_data = {
            'id': str(uuid.uuid4()),
            'name': data['name'],
            'email': data['email'],
            'phone': data['phone'],
            'company': data['company'],
            'requirements': data['requirements'],
            'additional_info': data.get('additional_info', ''),
            'product_category': data.get('product_category', ''),
            'quantity': data.get('quantity', ''),
            'budget': data.get('budget', ''),
            'timeline': data.get('timeline', ''),
            'status': 'new',
            'created_at': datetime.utcnow().isoformat()
        }
        
        rfq_collection.insert_one(rfq_data)
        
        # Send email to admin
        admin_email = os.getenv('ADMIN_EMAIL', 'admin@outrecouture.com')
        admin_subject = f"New RFQ from {data['name']} - {data['company']}"
        admin_body = f"""
    New RFQ Request Received:

    Name: {data['name']}
    Email: {data['email']}
    Phone: {data['phone']}
    Company: {data['company']}
    Requirements: {data['requirements']}
    Additional Info: {data.get('additional_info', 'N/A')}
    Product Category: {data.get('product_category', 'N/A')}
    Quantity: {data.get('quantity', 'N/A')}
    Budget: {data.get('budget', 'N/A')}
    Timeline: {data.get('timeline', 'N/A')}

    RFQ ID: {rfq_data['id']}
        """
        
        send_email(admin_email, admin_subject, admin_body)
        
        # Send confirmation email to user
        user_subject = "RFQ Submitted Successfully - Outre Couture"
        user_body = f"""
        Dear {data['name']},

        Thank you for submitting your RFQ (Request for Quote) to Outre Couture.

        Your RFQ details:
        - RFQ ID: {rfq_data['id']}
        - Company: {data['company']}
        - Requirements: {data['requirements']}

        We have received your request and our team will review it shortly. We will get back to you within 24-48 hours with a detailed quote.

        If you have any urgent questions, please don't hesitate to contact us.

        Best regards,
        Outre Couture Team
                """
        
        send_email(data['email'], user_subject, user_body)
        
        return jsonify({
            'success': True, 
            'message': 'RFQ submitted successfully',
            'rfq_id': rfq_data['id']
        }), 201
    except (ValueError, TypeError, ConnectionError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rfq', methods=['GET'])
def get_rfq_requests():
    """Get all RFQ requests (Admin only)"""
    try:
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))
        
        query = {}
        if status:
            query['status'] = status
        
        rfq_requests = list(rfq_collection.find(query, {'_id': 0}).sort('created_at', -1).skip(skip).limit(limit))
        
        return jsonify({
            'success': True,
            'rfq_requests': rfq_requests,
            'total': len(rfq_requests),
            'limit': limit,
            'skip': skip
        }), 200
    except (ValueError, TypeError, ConnectionError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/rfq/<rfq_id>', methods=['PUT'])
def update_rfq_status(rfq_id):
    """Update RFQ status (Admin only)"""
    try:
        data = request.get_json()
        
        if 'status' not in data:
            return jsonify({'success': False, 'error': 'Status is required'}), 400
        
        valid_statuses = ['new', 'reviewing', 'quoted', 'closed', 'won', 'lost']
        if data['status'] not in valid_statuses:
            return jsonify({'success': False, 'error': 'Invalid status'}), 400
        
        result = rfq_collection.update_one(
            {'id': rfq_id},
            {
                '$set': {
                    'status': data['status'],
                    'updated_at': datetime.utcnow().isoformat(),
                    'notes': data.get('notes', '')
                }
            }
        )
        
        if result.matched_count == 0:
            return jsonify({'success': False, 'error': 'RFQ not found'}), 404
        
        return jsonify({'success': True, 'message': 'RFQ status updated successfully'}), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== HEALTH CHECK ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        # Test MongoDB connection
        client.admin.command('ping')
        return jsonify({
            'success': True,
            'status': 'healthy',
            'environment': ENV,
            'base_url': BASE_URL,
            'database': 'connected',
            'timestamp': datetime.utcnow().isoformat()
        }), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({
            'success': False,
            'status': 'unhealthy',
            'environment': ENV,
            'base_url': BASE_URL,
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        }), 500

if __name__ == '__main__':
    print(f"Starting Outre Couture Backend in {ENV} mode")
    print(f"API will be available at: {BASE_URL}")
    print(f"Server will run on: {API_HOST}:{API_PORT}")
    app.run(debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true', 
            host=API_HOST, 
            port=API_PORT)
