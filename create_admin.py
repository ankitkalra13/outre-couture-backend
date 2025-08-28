#!/usr/bin/env python3
"""
Admin User Creation Script for Outre Couture Backend

This script helps you create admin users in the database manually.
Run this script to add admin users without going through the registration process.

Usage:
    python create_admin.py
"""

import os
import sys
import bcrypt
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
ENV = os.getenv('FLASK_ENV', 'development')
env_file = f'env.{ENV}'

if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"Loaded environment configuration from: {env_file}")
else:
    load_dotenv()
    print(f"Loaded default environment configuration")

# MongoDB Configuration
MONGO_URI = os.getenv('MONGO_URI', 'mongodb+srv://ankitkalra13:0yQ4N2JY1hJVXmyT@cluster0.j2yojqe.mongodb.net')
BCRYPT_ROUNDS = int(os.getenv('BCRYPT_ROUNDS', 12))

def hash_password(password):
    """Hash password using bcrypt"""
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode('utf-8'), salt)

def validate_password(password):
    """Validate password strength"""
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
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

def create_admin_user():
    """Create an admin user interactively"""
    try:
        # Connect to MongoDB
        client = MongoClient(MONGO_URI)
        db = client['outre_couture']
        users_collection = db['users']
        
        print("=== Outre Couture Admin User Creation ===\n")
        
        # Get user input
        username = input("Enter admin username: ").strip()
        if not username:
            print("Username cannot be empty!")
            return False
        
        # Check if username already exists
        existing_user = users_collection.find_one({'username': username})
        if existing_user:
            print(f"User '{username}' already exists!")
            return False
        
        email = input("Enter admin email: ").strip()
        if not email:
            print("Email cannot be empty!")
            return False
        
        if not validate_email(email):
            print("Invalid email format!")
            return False
        
        # Check if email already exists
        existing_email = users_collection.find_one({'email': email})
        if existing_email:
            print(f"Email '{email}' already exists!")
            return False
        
        # Get password
        while True:
            password = input("Enter admin password: ").strip()
            if not password:
                print("Password cannot be empty!")
                continue
            
            is_valid, message = validate_password(password)
            if not is_valid:
                print(f"Password validation failed: {message}")
                continue
            
            confirm_password = input("Confirm admin password: ").strip()
            if password != confirm_password:
                print("Passwords do not match!")
                continue
            
            break
        
        # Hash password
        hashed_password = hash_password(password)
        
        # Create admin user
        admin_user = {
            'username': username,
            'password': hashed_password,
            'email': email,
            'role': 'admin',
            'created_at': datetime.utcnow(),
            'last_login': None,
            'is_active': True
        }
        
        # Insert into database
        result = users_collection.insert_one(admin_user)
        
        if result.inserted_id:
            print(f"\n✅ Admin user '{username}' created successfully!")
            print(f"User ID: {result.inserted_id}")
            print(f"Role: admin")
            print(f"Email: {email}")
            print(f"Created at: {admin_user['created_at']}")
            print("\nYou can now use these credentials to access the admin panel.")
            return True
        else:
            print("❌ Failed to create admin user!")
            return False
            
    except Exception as e:
        print(f"❌ Error creating admin user: {e}")
        return False
    finally:
        if 'client' in locals():
            client.close()

def list_admin_users():
    """List all admin users"""
    try:
        client = MongoClient(MONGO_URI)
        db = client['outre_couture']
        users_collection = db['users']
        
        admin_users = list(users_collection.find({'role': 'admin'}, {'password': 0}))
        
        if admin_users:
            print("\n=== Current Admin Users ===")
            for user in admin_users:
                print(f"Username: {user['username']}")
                print(f"Email: {user['email']}")
                print(f"Created: {user['created_at']}")
                print(f"Active: {user.get('is_active', True)}")
                print("-" * 30)
        else:
            print("No admin users found.")
            
    except Exception as e:
        print(f"❌ Error listing admin users: {e}")
    finally:
        if 'client' in locals():
            client.close()

def main():
    """Main function"""
    print("Outre Couture Admin Management Tool")
    print("=" * 40)
    
    while True:
        print("\nOptions:")
        print("1. Create new admin user")
        print("2. List existing admin users")
        print("3. Exit")
        
        choice = input("\nEnter your choice (1-3): ").strip()
        
        if choice == '1':
            create_admin_user()
        elif choice == '2':
            list_admin_users()
        elif choice == '3':
            print("Goodbye!")
            break
        else:
            print("Invalid choice. Please try again.")

if __name__ == "__main__":
    main()
