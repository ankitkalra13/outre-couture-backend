#!/usr/bin/env python3
"""
Test script for Outre Couture Backend API
This script tests the main API endpoints to ensure they're working correctly.
"""

import os
import time
import requests
from dotenv import load_dotenv

# Load environment-specific configuration
ENV = os.getenv('FLASK_ENV', 'development')
env_file = f'env.{ENV}'

if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"Testing with environment configuration from: {env_file}")
else:
    load_dotenv()
    print("Testing with default environment configuration")

# API base URL from environment
BASE_URL = os.getenv('BASE_URL', 'http://localhost:5000/api')

def test_health_check():
    """Test health check endpoint"""
    print(f"Testing health check at: {BASE_URL}/health")
    try:
        response = requests.get(f'{BASE_URL}/health', timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Health check passed: {data['status']}")
            print(f"  Environment: {data.get('environment', 'unknown')}")
            print(f"  Base URL: {data.get('base_url', 'unknown')}")
            return True
        else:
            print(f"✗ Health check failed: {response.status_code}")
            return False
    except (ConnectionError, ValueError, TypeError) as e:
        print(f"✗ Health check error: {e}")
        return False

def test_categories():
    """Test categories endpoints"""
    print(f"\nTesting categories at: {BASE_URL}/categories")
    
    # Get categories
    try:
        response = requests.get(f'{BASE_URL}/categories', timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Get categories: {len(data.get('categories', []))} categories found")
        else:
            print(f"✗ Get categories failed: {response.status_code}")
            return False
    except (ConnectionError, ValueError, TypeError) as e:
        print(f"✗ Get categories error: {e}")
        return False
    
    # Create a test category
    test_category = {
        'name': 'Test Category',
        'description': 'This is a test category for API testing'
    }
    
    try:
        response = requests.post(
            f'{BASE_URL}/categories',
            json=test_category,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        if response.status_code == 201:
            data = response.json()
            print(f"✓ Create category: {data['category']['name']}")
            return data['category']['id']
        else:
            print(f"✗ Create category failed: {response.status_code}")
            return None
    except (ConnectionError, ValueError, TypeError) as e:
        print(f"✗ Create category error: {e}")
        return None

def test_products(category_id):
    """Test products endpoints"""
    print(f"\nTesting products at: {BASE_URL}/products")
    
    # Get products
    try:
        response = requests.get(f'{BASE_URL}/products', timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Get products: {len(data.get('products', []))} products found")
        else:
            print(f"✗ Get products failed: {response.status_code}")
            return None
    except (ConnectionError, ValueError, TypeError) as e:
        print(f"✗ Get products error: {e}")
        return None
    
    # Create a test product
    test_product = {
        'name': 'Test Product',
        'category_id': category_id,
        'price': 99.99,
        'description': 'This is a test product for API testing',
        'images': ['test_image_1.jpg'],
        'specifications': {
            'material': 'Test Material',
            'color': 'Test Color'
        }
    }
    
    try:
        response = requests.post(
            f'{BASE_URL}/products',
            json=test_product,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        if response.status_code == 201:
            data = response.json()
            print(f"✓ Create product: {data['product']['name']} - ${data['product']['price']}")
            return data['product']['id']
        else:
            print(f"✗ Create product failed: {response.status_code}")
            return None
    except (ConnectionError, ValueError, TypeError) as e:
        print(f"✗ Create product error: {e}")
        return None

def test_rfq():
    """Test RFQ endpoint"""
    print(f"\nTesting RFQ at: {BASE_URL}/rfq")
    
    test_rfq = {
        'name': 'Test Customer',
        'email': 'test@example.com',
        'phone': '+1234567890',
        'company': 'Test Company',
        'requirements': 'This is a test RFQ for API testing',
        'product_category': 'Test Category',
        'quantity': '10 pieces',
        'budget': '$1000',
        'timeline': '1 month'
    }
    
    try:
        response = requests.post(
            f'{BASE_URL}/rfq',
            json=test_rfq,
            headers={'Content-Type': 'application/json'},
            timeout=10
        )
        if response.status_code == 201:
            data = response.json()
            print(f"✓ Submit RFQ: {data['message']}")
            print(f"  RFQ ID: {data['rfq_id']}")
            return data['rfq_id']
        else:
            print(f"✗ Submit RFQ failed: {response.status_code}")
            return None
    except (ConnectionError, ValueError, TypeError) as e:
        print(f"✗ Submit RFQ error: {e}")
        return None

def test_get_rfq():
    """Test getting RFQ requests"""
    print(f"\nTesting get RFQ requests at: {BASE_URL}/rfq")
    
    try:
        response = requests.get(f'{BASE_URL}/rfq', timeout=10)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ Get RFQ requests: {len(data.get('rfq_requests', []))} requests found")
            return True
        else:
            print(f"✗ Get RFQ requests failed: {response.status_code}")
            return False
    except (requests.RequestException, ValueError, TypeError) as e:
        print(f"✗ Get RFQ requests error: {e}")
        return False

def main():
    """Main test function"""
    print("=" * 60)
    print(f"Outre Couture Backend API Test - {ENV.upper()} Environment")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Environment: {ENV}")
    print("=" * 60)
    
    # Wait a moment for the server to be ready
    print("Waiting for server to be ready...")
    time.sleep(2)
    
    # Test health check
    if not test_health_check():
        print(f"\n✗ Server is not responding at {BASE_URL}")
        print("Please make sure the Flask app is running.")
        return
    
    # Test categories
    category_id = test_categories()
    if not category_id:
        print("\n✗ Category test failed. Stopping tests.")
        return
    
    # Test products
    product_id = test_products(category_id)
    if not product_id:
        print("\n✗ Product test failed. Stopping tests.")
        return
    
    # Test RFQ
    rfq_id = test_rfq()
    if not rfq_id:
        print("\n✗ RFQ test failed. Stopping tests.")
        return
    
    # Test get RFQ
    test_get_rfq()
    
    print("\n" + "=" * 60)
    print(f"✓ All tests completed successfully in {ENV.upper()} environment!")
    print("=" * 60)
    print(f"\nAPI endpoints are working correctly at: {BASE_URL}")
    print("You can now use the admin panel and website with confidence.")

if __name__ == '__main__':
    main()
