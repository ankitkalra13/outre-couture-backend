"""
Outre Couture Backend API

A Flask-based REST API for Outre Couture's admin panel and website.
Provides product management, category management, and RFQ handling with email notifications.
"""

from werkzeug.middleware.proxy_fix import ProxyFix
import json
import os
import re
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
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError

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
API_PORT = int(os.getenv('PORT', os.getenv('API_PORT', 5000)))

app = Flask(__name__)

# Configure ProxyFix for handling proxy headers (needed for Render/production)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# CORS Configuration - Use environment variable for frontend URL
FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

# For production with custom domains, use wildcard CORS
# This is necessary because Render's proxy can cause issues with strict CORS
CORS(app, 
     resources={r"/api/*": {"origins": "*"}},
     supports_credentials=False,
     allow_headers=['Content-Type', 'Authorization', 'X-Requested-With', 'Accept'],
     methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
     expose_headers=['Content-Type', 'Authorization'])

# MongoDB Configuration
MONGO_URI = os.getenv('MONGO_URI')
if not MONGO_URI:
    raise ValueError("MONGO_URI environment variable is required")
client = MongoClient(MONGO_URI)

# Database name - extract from MONGO_URI or use default
DB_NAME = os.getenv('DB_NAME', 'outre_couture')
db = client[DB_NAME]

# Collections
products_collection = db['products']
categories_collection = db['categories']
media_pages_collection = db['media_pages']
rfq_collection = db['rfq_requests']

# Email Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv(
    'MAIL_USE_TLS', 'true').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_DEFAULT_SENDER')

mail = Mail(app)

# JWT Configuration
app.config['JWT_SECRET_KEY'] = os.getenv(
    'JWT_SECRET_KEY', secrets.token_urlsafe(32))
app.config['JWT_ALGORITHM'] = 'HS256'
app.config['JWT_EXPIRATION_HOURS'] = int(os.getenv('JWT_EXPIRATION_HOURS', 24))
app.config['JWT_REFRESH_EXPIRATION_DAYS'] = int(
    os.getenv('JWT_REFRESH_EXPIRATION_DAYS', 7))

# Security Configuration
app.config['BCRYPT_ROUNDS'] = int(os.getenv('BCRYPT_ROUNDS', 12))
app.config['PASSWORD_MIN_LENGTH'] = int(os.getenv('PASSWORD_MIN_LENGTH', 8))
app.config['MAX_LOGIN_ATTEMPTS'] = int(os.getenv('MAX_LOGIN_ATTEMPTS', 5))
app.config['LOGIN_LOCKOUT_MINUTES'] = int(
    os.getenv('LOGIN_LOCKOUT_MINUTES', 15))

# Collections
users_collection = db['users']

# In-memory storage for login attempts (in production, use Redis)
login_attempts = {}
account_lockouts = {}

# AWS S3 / CloudFront Configuration
AWS_REGION = os.getenv('AWS_REGION', 'ap-south-1')
AWS_S3_BUCKET = os.getenv('AWS_S3_BUCKET')
AWS_CDN_BASE_URL = os.getenv('AWS_CDN_BASE_URL', '').rstrip('/')
ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
ALLOWED_IMAGE_EXTENSIONS = {'jpg', 'jpeg', 'png', 'webp'}
ALLOWED_UPLOAD_ROOT_FOLDERS = {'products', 'site', 'categories'}
PRESIGNED_URL_EXPIRY_SECONDS = 300

_s3_client = None


def get_s3_client():
    """Return a cached S3 client, or None if AWS credentials are not configured."""
    global _s3_client
    if _s3_client is not None:
        return _s3_client

    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    if not access_key or not secret_key or not AWS_S3_BUCKET:
        return None

    _s3_client = boto3.client(
        's3',
        region_name=AWS_REGION,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4'),
    )
    return _s3_client


def validate_image_urls(images):
    """Validate product image URLs before saving to MongoDB."""
    if not isinstance(images, list):
        return False, 'Images must be an array'

    for image in images:
        if not isinstance(image, str) or not image.strip():
            return False, 'Each image must be a non-empty URL string'
        if image.startswith('http://') or image.startswith('https://'):
            continue
        return False, 'Image URLs must be full http(s) URLs'

    return True, None


def extract_s3_key_from_url(image_url):
    """Extract the S3 object key from a CloudFront or S3 URL."""
    if not image_url or not AWS_CDN_BASE_URL:
        return None

    if image_url.startswith(f'{AWS_CDN_BASE_URL}/'):
        return image_url[len(AWS_CDN_BASE_URL) + 1:]

    bucket_host = f'{AWS_S3_BUCKET}.s3.{AWS_REGION}.amazonaws.com'
    if image_url.startswith(f'https://{bucket_host}/'):
        return image_url[len(f'https://{bucket_host}/'):]

    return None


def sanitize_path_segment(value):
    """Convert a label or slug into a safe S3 path segment."""
    if not value:
        return ''
    slug = str(value).lower().strip().replace(' ', '-').replace('_', '-')
    slug = re.sub(r'[^a-z0-9-]', '', slug)
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug[:80]


def build_upload_key(folder, filename, data=None):
    """Build an S3 object key based on upload folder and optional path metadata."""
    data = data or {}
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'webp'
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValueError('Invalid file extension')

    file_id = str(uuid.uuid4())

    if folder == 'products':
        main_slug = sanitize_path_segment(data.get('mainCategorySlug'))
        sub_slug = sanitize_path_segment(data.get('subCategorySlug'))

        if not main_slug or not sub_slug:
            sub_category_id = (data.get('subCategoryId') or '').strip()
            if sub_category_id:
                sub_category = categories_collection.find_one(
                    {'id': sub_category_id, 'type': 'sub'},
                    {'id': 1, 'slug': 1, 'name': 1, 'main_category_id': 1, '_id': 0}
                )
                if sub_category:
                    sub_slug = sanitize_path_segment(
                        sub_category.get('slug') or sub_category.get('name'))
                    main_category = categories_collection.find_one(
                        {'id': sub_category.get('main_category_id'), 'type': 'main'},
                        {'slug': 1, 'name': 1, '_id': 0}
                    )
                    if main_category:
                        main_slug = sanitize_path_segment(
                            main_category.get('slug') or main_category.get('name'))

        if not main_slug or not sub_slug:
            raise ValueError('mainCategorySlug and subCategorySlug are required for product uploads')

        return f"products/{main_slug}/{sub_slug}/{file_id}.{ext}", None

    if folder == 'site':
        page_slug = sanitize_path_segment(
            data.get('pageSlug') or data.get('pageName'))
        if not page_slug:
            raise ValueError('pageSlug is required for site uploads')
        return f"site/{page_slug}/{file_id}.{ext}", None

    if folder == 'categories':
        return f"categories/{file_id}.{ext}", None

    raise ValueError('Invalid upload folder')


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
        payload = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=[
                             app.config['JWT_ALGORITHM']])
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
            remaining_minutes = int(
                (lockout_time - datetime.utcnow()).total_seconds() / 60)
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
        lockout_time = datetime.utcnow(
        ) + timedelta(minutes=app.config['LOGIN_LOCKOUT_MINUTES'])
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
        existing_user = users_collection.find_one(
            {'$or': [{'username': data['username']}, {'email': data['email']}]})
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
        access_token = generate_token(
            result.inserted_id, data['username'], user['role'])
        refresh_token = generate_refresh_token(
            result.inserted_id, data['username'], user['role'])

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
            # 423 Locked
            return jsonify({'success': False, 'error': lockout_message}), 423

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
        access_token = generate_token(
            user['_id'], user['username'], user.get('role', 'user'))
        refresh_token = generate_refresh_token(
            user['_id'], user['username'], user.get('role', 'user'))

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
            payload = jwt.decode(data['refresh_token'], app.config['JWT_SECRET_KEY'], algorithms=[
                                 app.config['JWT_ALGORITHM']])
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
        access_token = generate_token(
            user['_id'], user['username'], user.get('role', 'user'))
        refresh_token = generate_refresh_token(
            user['_id'], user['username'], user.get('role', 'user'))

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
        main_categories = list(categories_collection.find(
            {'type': 'main'}, {'_id': 0}))
        # Convert to JSON serializable format
        categories_json = convert_to_json_serializable(main_categories)
        return jsonify({'success': True, 'categories': categories_json}), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/categories/sub/<main_category_slug>', methods=['GET'])
def get_sub_categories(main_category_slug):
    """Get sub-categories for a specific main category"""
    try:
        # First find the main category (by slug or name)
        main_category_title = main_category_slug.replace('-', ' ').title()
        main_category = categories_collection.find_one({
            'type': 'main',
            '$or': [
                {'slug': main_category_slug},
                {'name': {'$regex': f'^{main_category_title}$', '$options': 'i'}},
                {'name': {'$regex': f'^{main_category_slug}$', '$options': 'i'}},
            ]
        })
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
            main_category = categories_collection.find_one(
                {'id': data['main_category_id'], 'type': 'main'})
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
        sub_categories_by_main_json = convert_to_json_serializable(
            sub_categories_by_main)

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
                conflict_category = categories_collection.find_one(
                    {'name': data['name'].strip()})
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
        updated_category = categories_collection.find_one(
            {'id': category_id}, {'_id': 0})
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

        category_type = existing_category.get('type', 'main')

        if category_type == 'main':
            sub_category_ids = [
                sub['id'] for sub in categories_collection.find(
                    {'main_category_id': category_id, 'type': 'sub'},
                    {'id': 1, '_id': 0}
                )
            ]

            product_filters = [
                {'main_category_slug': existing_category.get('slug')},
                {'main_category_name': existing_category.get('name')},
            ]
            if sub_category_ids:
                product_filters.append({'category_id': {'$in': sub_category_ids}})

            products_using_category = products_collection.count_documents(
                {'$or': product_filters}
            )
            if products_using_category > 0:
                return jsonify({
                    'success': False,
                    'error': (
                        f'Cannot delete main category. {products_using_category} product(s) '
                        'are assigned under this category.'
                    )
                }), 400
        else:
            products_using_category = products_collection.count_documents(
                {'category_id': category_id})
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

# ==================== UPLOAD APIs ====================


@app.route('/api/media-pages', methods=['GET'])
@require_admin
def get_media_pages():
    """List media library pages for site image uploads."""
    try:
        pages = list(media_pages_collection.find(
            {}, {'_id': 0}).sort('name', 1))
        pages_json = convert_to_json_serializable(pages)
        return jsonify({'success': True, 'pages': pages_json}), 200
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/media-pages', methods=['POST'])
@require_admin
def create_media_page():
    """Create a page entry for organizing site media uploads."""
    try:
        data = request.get_json() or {}
        name = (data.get('name') or '').strip()

        if len(name) < 2:
            return jsonify({'success': False, 'error': 'Page name must be at least 2 characters long'}), 400

        slug = sanitize_path_segment(name)
        if not slug:
            return jsonify({'success': False, 'error': 'Invalid page name'}), 400

        existing_page = media_pages_collection.find_one({'slug': slug})
        if existing_page:
            return jsonify({'success': False, 'error': 'A page with this name already exists'}), 400

        page = {
            'id': str(uuid.uuid4()),
            'name': name,
            'slug': slug,
            'created_at': datetime.utcnow().isoformat(),
            'created_by': str(request.user['user_id']),
        }

        media_pages_collection.insert_one(page)
        page_json = convert_to_json_serializable(page)
        return jsonify({'success': True, 'page': page_json}), 201
    except (ConnectionError, ValueError, TypeError) as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/uploads/presign', methods=['POST'])
@require_admin
def presign_upload():
    """Generate a presigned PUT URL for direct browser upload to S3."""
    try:
        data = request.get_json() or {}
        filename = (data.get('filename') or '').strip()
        content_type = (data.get('contentType') or '').strip()
        folder = (data.get('folder') or 'products').strip()

        if not filename or not content_type:
            return jsonify({'success': False, 'error': 'filename and contentType are required'}), 400

        if content_type not in ALLOWED_IMAGE_TYPES:
            return jsonify({'success': False, 'error': 'Invalid file type. Allowed: JPEG, PNG, WebP'}), 400

        if folder not in ALLOWED_UPLOAD_ROOT_FOLDERS:
            return jsonify({'success': False, 'error': 'Invalid upload folder'}), 400

        if not AWS_CDN_BASE_URL:
            return jsonify({'success': False, 'error': 'Upload service not configured (AWS_CDN_BASE_URL missing)'}), 500

        s3_client = get_s3_client()
        if not s3_client:
            return jsonify({'success': False, 'error': 'Upload service not configured (AWS credentials missing)'}), 500

        try:
            key, _ = build_upload_key(folder, filename, data)
        except ValueError as exc:
            return jsonify({'success': False, 'error': str(exc)}), 400

        ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else 'webp'
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            return jsonify({'success': False, 'error': 'Invalid file extension'}), 400

        upload_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': AWS_S3_BUCKET,
                'Key': key,
                'ContentType': content_type,
                'CacheControl': 'public, max-age=31536000, immutable',
            },
            ExpiresIn=PRESIGNED_URL_EXPIRY_SECONDS,
        )

        public_url = f"{AWS_CDN_BASE_URL}/{key}"

        return jsonify({
            'success': True,
            'uploadUrl': upload_url,
            'publicUrl': public_url,
            'key': key,
        }), 200
    except ClientError as e:
        return jsonify({'success': False, 'error': f'AWS error: {e.response["Error"]["Message"]}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/uploads', methods=['DELETE'])
@require_admin
def delete_upload():
    """Delete an uploaded object from S3 by key or CloudFront URL."""
    try:
        data = request.get_json() or {}
        key = (data.get('key') or '').strip()
        image_url = (data.get('url') or '').strip()

        if not key and image_url:
            key = extract_s3_key_from_url(image_url)

        if not key:
            return jsonify({'success': False, 'error': 'key or url is required'}), 400

        if '..' in key or key.startswith('/'):
            return jsonify({'success': False, 'error': 'Invalid key'}), 400

        root_folder = key.split('/', 1)[0]
        if root_folder not in ALLOWED_UPLOAD_ROOT_FOLDERS:
            return jsonify({'success': False, 'error': 'Invalid upload key'}), 400

        s3_client = get_s3_client()
        if not s3_client:
            return jsonify({'success': False, 'error': 'Upload service not configured'}), 500

        s3_client.delete_object(Bucket=AWS_S3_BUCKET, Key=key)

        return jsonify({'success': True, 'message': 'Image deleted successfully', 'key': key}), 200
    except ClientError as e:
        return jsonify({'success': False, 'error': f'AWS error: {e.response["Error"]["Message"]}'}), 500
    except Exception as e:
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
        sub_category = categories_collection.find_one(
            {'id': data['category_id'], 'type': 'sub'})
        if not sub_category:
            return jsonify({'success': False, 'error': 'Invalid category_id - must be a sub-category'}), 400

        # Get main category info
        main_category = categories_collection.find_one(
            {'id': sub_category['main_category_id'], 'type': 'main'})
        if not main_category:
            return jsonify({'success': False, 'error': 'Invalid main category reference'}), 400

        # Validate images array
        images = data.get('images', [])
        if not images:
            return jsonify({'success': False, 'error': 'At least one product image is required'}), 400
        is_valid_images, image_error = validate_image_urls(images)
        if not is_valid_images:
            return jsonify({'success': False, 'error': image_error}), 400

        # SEO fields with defaults
        seo_title = data.get('seo_title', data['name'].strip())
        seo_description = data.get(
            'seo_description', data['description'].strip()[:160])
        seo_keywords = data.get('seo_keywords', '')
        seo_slug = data.get(
            'seo_slug', data['name'].strip().lower().replace(' ', '-'))

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
            # SEO fields
            'seo_title': seo_title,
            'seo_description': seo_description,
            'seo_keywords': seo_keywords,
            'seo_slug': seo_slug,
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
        is_active_param = request.args.get('is_active', 'true')
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))

        # Build query
        query = {}
        if is_active_param.lower() != 'all':
            query['is_active'] = is_active_param.lower() == 'true'
        if category_id:
            query['category_id'] = category_id

        # Add main category filtering
        main_category_name = request.args.get('main_category_name')
        if main_category_name:
            query['main_category_name'] = main_category_name

        # Add search filtering
        search = request.args.get('search')
        if search:
            query['$or'] = [
                {'name': {'$regex': search, '$options': 'i'}},
                {'description': {'$regex': search, '$options': 'i'}},
                {'seo_keywords': {'$regex': search, '$options': 'i'}},
                {'seo_title': {'$regex': search, '$options': 'i'}}
            ]

        # Apply sorting
        sort_by = request.args.get('sortBy', 'name')
        sort_options = {
            'name': [('name', 1)],
            'name_desc': [('name', -1)],
            'newest': [('created_at', -1)],
            'oldest': [('created_at', 1)]
        }

        sort_criteria = sort_options.get(sort_by, [('name', 1)])

        total = products_collection.count_documents(query)
        products = list(products_collection.find(query, {'_id': 0}).sort(
            sort_criteria).skip(skip).limit(limit))

        # Convert to JSON serializable format
        products_json = convert_to_json_serializable(products)

        return jsonify({
            'success': True,
            'products': products_json,
            'total': total,
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
        is_active_param = request.args.get('is_active', 'true')
        limit = int(request.args.get('limit', 50))
        skip = int(request.args.get('skip', 0))

        # Build query - check both main_category_slug and main_category_name
        main_category_title = main_category_slug.replace('-', ' ').title()

        query_parts = [{
            '$or': [
                {'main_category_slug': main_category_slug},
                {'main_category_name': main_category_title}
            ]
        }]
        if is_active_param.lower() != 'all':
            query_parts.append({'is_active': is_active_param.lower() == 'true'})
        if sub_category_id:
            query_parts.append({'category_id': sub_category_id})

        search = request.args.get('search')
        if search:
            query_parts.append({
                '$or': [
                    {'name': {'$regex': search, '$options': 'i'}},
                    {'description': {'$regex': search, '$options': 'i'}},
                ]
            })

        query = query_parts[0] if len(query_parts) == 1 else {'$and': query_parts}

        sort_by = request.args.get('sortBy', 'name')
        sort_options = {
            'name': [('name', 1)],
            'name_desc': [('name', -1)],
            'newest': [('created_at', -1)],
            'oldest': [('created_at', 1)]
        }
        sort_criteria = sort_options.get(sort_by, [('name', 1)])

        total = products_collection.count_documents(query)
        products = list(products_collection.find(
            query, {'_id': 0}).sort(sort_criteria).skip(skip).limit(limit))

        # Convert to JSON serializable format
        products_json = convert_to_json_serializable(products)

        return jsonify({
            'success': True,
            'products': products_json,
            'total': total,
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
            category = categories_collection.find_one(
                {'id': data['category_id']})
            if not category:
                return jsonify({'success': False, 'error': 'Invalid category_id'}), 400
            update_data['category_id'] = data['category_id']
            update_data['category_name'] = category['name']

        if 'description' in data:
            update_data['description'] = data['description']
        if 'images' in data:
            if not data['images']:
                return jsonify({'success': False, 'error': 'At least one product image is required'}), 400
            is_valid_images, image_error = validate_image_urls(data['images'])
            if not is_valid_images:
                return jsonify({'success': False, 'error': image_error}), 400
            update_data['images'] = data['images']
        if 'specifications' in data:
            update_data['specifications'] = data['specifications']
        if 'is_active' in data:
            update_data['is_active'] = data['is_active']

        # SEO fields
        if 'seo_title' in data:
            update_data['seo_title'] = data['seo_title']
        if 'seo_description' in data:
            update_data['seo_description'] = data['seo_description']
        if 'seo_keywords' in data:
            update_data['seo_keywords'] = data['seo_keywords']
        if 'seo_slug' in data:
            update_data['seo_slug'] = data['seo_slug']

        products_collection.update_one(
            {'id': product_id},
            {'$set': update_data}
        )

        # Get updated product
        updated_product = products_collection.find_one(
            {'id': product_id}, {'_id': 0})
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


@app.route('/api/products/slug/<main_category>/<slug>', methods=['GET'])
def get_product_by_slug(main_category, slug):
    """Get a product by its SEO slug and main category"""
    try:
        # Find product by slug and main category (try multiple approaches)
        product = None

        # First try: exact match with main_category_slug
        product = products_collection.find_one({
            'seo_slug': slug,
            'main_category_slug': main_category,
            'is_active': True
        }, {'_id': 0})

        # Second try: match with main_category_name (case-insensitive)
        if not product:
            product = products_collection.find_one({
                'seo_slug': slug,
                'main_category_name': {'$regex': f'^{main_category}$', '$options': 'i'},
                'is_active': True
            }, {'_id': 0})

        # Third try: find by slug only (fallback)
        if not product:
            product = products_collection.find_one({
                'seo_slug': slug,
                'is_active': True
            }, {'_id': 0})

        # Fourth try: search by generated slug from product name (if seo_slug doesn't exist)
        if not product:
            all_products = list(products_collection.find({
                'is_active': True,
                'main_category_slug': main_category
            }, {'_id': 0}))

            for p in all_products:
                # Generate slug from product name
                product_name_slug = p.get(
                    'name', '').lower().strip().replace(' ', '-')
                product_name_slug = re.sub(
                    r'[^a-z0-9-]', '', product_name_slug)
                product_name_slug = re.sub(
                    r'-+', '-', product_name_slug).strip('-')

                # Check if generated slug matches
                if product_name_slug == slug:
                    product = p
                    break

        # Fifth try: search by product ID (if slug looks like an ID)
        if not product:
            product = products_collection.find_one({
                'id': slug,
                'is_active': True
            }, {'_id': 0})

        if not product:
            return jsonify({'success': False, 'error': 'Product not found'}), 404

        # Convert to JSON serializable format
        product_json = convert_to_json_serializable(product)
        return jsonify({'success': True, 'product': product_json}), 200

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

        total = rfq_collection.count_documents(query)
        rfq_requests = list(rfq_collection.find(query, {'_id': 0}).sort(
            'created_at', -1).skip(skip).limit(limit))

        return jsonify({
            'success': True,
            'rfq_requests': rfq_requests,
            'total': total,
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

        valid_statuses = ['new', 'reviewing',
                          'quoted', 'closed', 'won', 'lost']
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
