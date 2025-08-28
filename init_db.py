#!/usr/bin/env python3
"""
Database initialization script for Outre Couture Backend
This script creates the new hierarchical category structure with main categories and sub-categories.
"""

import os
import uuid
from datetime import datetime, timezone
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# MongoDB Configuration
MONGO_URI = os.getenv('MONGO_URI', 'mongodb+srv://ankitkalra13:0yQ4N2JY1hJVXmyT@cluster0.j2yojqe.mongodb.net')
client = MongoClient(MONGO_URI)
db = client['outre_couture']

# Collections
categories_collection = db['categories']
products_collection = db['products']

def create_hierarchical_categories():
    """Create the new hierarchical category structure"""
    
    # Main categories with their sub-categories
    main_categories = [
        {
            'id': str(uuid.uuid4()),
            'name': 'Men',
            'type': 'main',
            'description': 'Men\'s fashion and clothing',
            'slug': 'men',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'sub_categories': [
                'Bottom', 'Formal Wear', 'Jackets', 'Shirts', 'Sports Wear', 'T-shirts'
            ]
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'Women',
            'type': 'main',
            'description': 'Women\'s fashion and clothing',
            'slug': 'women',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'sub_categories': [
                'Beach-Kaftans', 'Tops', 'Short Dress', 'Long Dress', 'Scarf', 'Skirts-Pants', 'Jackets-Coat'
            ]
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'Accessories',
            'type': 'main',
            'description': 'Fashion accessories and jewelry',
            'slug': 'accessories',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'sub_categories': [
                'Clothing Accessories', 'Jewelry', 'Handbag & Wallet Accessories'
            ]
        },
        {
            'id': str(uuid.uuid4()),
            'name': 'Bags',
            'type': 'main',
            'description': 'Various types of bags and luggage',
            'slug': 'bags',
            'created_at': datetime.now(timezone.utc).isoformat(),
            'sub_categories': [
                'Backpacks', 'Delivery Bags', 'Laptops Bags', 'Leather Style', 'Macrame & Beach', 'Messenger Bags', 'Paper Packing', 'Tote Bags'
            ]
        }
    ]
    
    # Create main categories
    main_category_ids = {}
    for main_cat in main_categories:
        # Check if main category already exists
        existing = categories_collection.find_one({'name': main_cat['name'], 'type': 'main'})
        if not existing:
            categories_collection.insert_one(main_cat)
            print(f"Created main category: {main_cat['name']}")
            main_category_ids[main_cat['name']] = main_cat['id']
        else:
            print(f"Main category already exists: {main_cat['name']}")
            main_category_ids[main_cat['name']] = existing['id']
    
    # Create sub-categories
    sub_categories = []
    for main_cat in main_categories:
        main_id = main_category_ids[main_cat['name']]
        for sub_cat_name in main_cat['sub_categories']:
            sub_cat = {
                'id': str(uuid.uuid4()),
                'name': sub_cat_name,
                'type': 'sub',
                'main_category_id': main_id,
                'main_category_name': main_cat['name'],
                'main_category_slug': main_cat['slug'],
                'description': f'{sub_cat_name} under {main_cat["name"]}',
                'slug': sub_cat_name.lower().replace(' ', '-').replace('&', 'and'),
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            sub_categories.append(sub_cat)
    
    # Insert sub-categories
    for sub_cat in sub_categories:
        existing = categories_collection.find_one({
            'name': sub_cat['name'], 
            'type': 'sub', 
            'main_category_id': sub_cat['main_category_id']
        })
        if not existing:
            categories_collection.insert_one(sub_cat)
            print(f"Created sub-category: {sub_cat['name']} under {sub_cat['main_category_name']}")
        else:
            print(f"Sub-category already exists: {sub_cat['name']} under {sub_cat['main_category_name']}")
    
    return main_category_ids, sub_categories

def create_sample_products(main_category_ids):
    """Create sample products for each sub-category"""
    
    # Get all sub-categories
    sub_categories = list(categories_collection.find({'type': 'sub'}))
    
    # Sample products for Men's category
    men_products = [
        {
            'id': str(uuid.uuid4()),
            'name': 'Classic Denim Jeans',
            'category_id': next(cat['id'] for cat in sub_categories if cat['name'] == 'Bottom' and cat['main_category_name'] == 'Men'),
            'category_name': 'Bottom',
            'main_category_name': 'Men',
            'description': 'Premium denim jeans with perfect fit and comfort. Made from high-quality cotton denim.',
            'images': ['men_jeans_1.jpg', 'men_jeans_2.jpg'],
            'specifications': {
                'material': '100% Cotton Denim',
                'color': 'Blue',
                'fit': 'Regular Fit',
                'waist_sizes': '30", 32", 34", 36", 38"',
                'length': '32", 34"'
            },
            'is_active': True,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
    ]
    
    # Sample products for Women's category
    women_products = [
        {
            'id': str(uuid.uuid4()),
            'name': 'Elegant Evening Dress',
            'category_id': next(cat['id'] for cat in sub_categories if cat['name'] == 'Long Dress' and cat['main_category_name'] == 'Women'),
            'category_name': 'Long Dress',
            'main_category_name': 'Women',
            'description': 'Stunning evening dress perfect for special occasions. Flowing design with elegant details.',
            'images': ['women_dress_1.jpg', 'women_dress_2.jpg'],
            'specifications': {
                'material': 'Silk Blend',
                'color': 'Black, Navy',
                'length': 'Floor Length',
                'sizes': 'XS, S, M, L, XL',
                'style': 'A-Line'
            },
            'is_active': True,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
    ]
    
    # Sample products for Accessories category
    accessories_products = [
        {
            'id': str(uuid.uuid4()),
            'name': 'Pearl Necklace Set',
            'category_id': next(cat['id'] for cat in sub_categories if cat['name'] == 'Jewelry' and cat['main_category_name'] == 'Accessories'),
            'category_name': 'Jewelry',
            'main_category_name': 'Accessories',
            'description': 'Elegant freshwater pearl necklace with matching earrings. Perfect for formal occasions.',
            'images': ['jewelry_pearl_1.jpg', 'jewelry_pearl_2.jpg'],
            'specifications': {
                'material': 'Freshwater Pearls',
                'color': 'White',
                'length': '18 inches',
                'clasp': 'Lobster Clasp',
                'includes': 'Necklace and Earrings'
            },
            'is_active': True,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
    ]
    
    # Sample products for Bags category
    bags_products = [
        {
            'id': str(uuid.uuid4()),
            'name': 'Leather Messenger Bag',
            'category_id': next(cat['id'] for cat in sub_categories if cat['name'] == 'Messenger Bags' and cat['main_category_name'] == 'Bags'),
            'category_name': 'Messenger Bags',
            'main_category_name': 'Bags',
            'description': 'Professional leather messenger bag perfect for work and travel. Multiple compartments for organization.',
            'images': ['bag_messenger_1.jpg', 'bag_messenger_2.jpg'],
            'specifications': {
                'material': 'Full-grain Leather',
                'color': 'Brown, Black',
                'size': 'Medium',
                'compartments': '3',
                'laptop_sleeve': 'Yes',
                'strap': 'Adjustable'
            },
            'is_active': True,
            'created_at': datetime.now(timezone.utc).isoformat(),
            'updated_at': datetime.now(timezone.utc).isoformat()
        }
    ]
    
    # Combine all products
    all_products = men_products + women_products + accessories_products + bags_products
    
    # Insert products
    for product in all_products:
        # Check if product already exists
        existing = products_collection.find_one({'name': product['name']})
        if not existing:
            products_collection.insert_one(product)
            print(f"Created product: {product['name']} - {product['category_name']}")
        else:
            print(f"Product already exists: {product['name']}")

def main():
    """Main initialization function"""
    print("Initializing Outre Couture Database with new category structure...")
    
    try:
        # Test database connection
        client.admin.command('ping')
        print("✓ Database connection successful")
        
        # Clear existing data (optional - comment out if you want to keep existing data)
        print("\nClearing existing categories and products...")
        categories_collection.delete_many({})
        products_collection.delete_many({})
        print("✓ Cleared existing data")
        
        # Create hierarchical categories
        print("\nCreating hierarchical categories...")
        main_category_ids, sub_categories = create_hierarchical_categories()
        
        # Create sample products
        print("\nCreating sample products...")
        create_sample_products(main_category_ids)
        
        print("\n✓ Database initialization completed successfully!")
        print(f"\nCreated {len(main_category_ids)} main categories and {len(sub_categories)} sub-categories")
        print("\nYou can now start the Flask application with: python app.py")
        
    except (ConnectionError, ValueError, TypeError) as e:
        print(f"✗ Error initializing database: {e}")
        print("Please make sure MongoDB is running and accessible")

if __name__ == '__main__':
    main()
