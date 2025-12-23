#!/usr/bin/env python3
"""
Migration script to add SEO fields to existing products
Run this script to update existing products with default SEO values
"""

import os
import sys
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


def migrate_products():
    """Add SEO fields to existing products"""
    try:
        # Connect to MongoDB
        mongo_uri = os.getenv('MONGO_URI')
        if not mongo_uri:
            print("Error: MONGO_URI environment variable is required")
            sys.exit(1)

        client = MongoClient(mongo_uri)
        DB_NAME = os.getenv('DB_NAME', 'outre_couture')
        db = client[DB_NAME]
        products_collection = db['products']

        print("Connected to MongoDB successfully")

        # Find products without SEO fields
        products_without_seo = products_collection.find({
            '$or': [
                {'seo_title': {'$exists': False}},
                {'seo_description': {'$exists': False}},
                {'seo_keywords': {'$exists': False}},
                {'seo_slug': {'$exists': False}}
            ]
        })

        count = 0
        for product in products_without_seo:
            # Generate default SEO values
            seo_title = product.get('name', 'Product')
            seo_description = product.get('description', '')[
                :160] if product.get('description') else ''
            seo_keywords = f"{product.get('category_name', '')}, {product.get('main_category_name', '')}, fashion, luxury"
            seo_slug = product.get('name', 'product').lower().replace(' ', '-')

            # Update product with SEO fields
            result = products_collection.update_one(
                {'id': product['id']},
                {
                    '$set': {
                        'seo_title': seo_title,
                        'seo_description': seo_description,
                        'seo_keywords': seo_keywords,
                        'seo_slug': seo_slug,
                        'updated_at': datetime.utcnow().isoformat()
                    }
                }
            )

            if result.modified_count > 0:
                count += 1
                print(f"Updated product: {product.get('name', 'Unknown')}")

        print(f"\nMigration completed successfully!")
        print(f"Updated {count} products with SEO fields")

        # Verify migration
        total_products = products_collection.count_documents({})
        products_with_seo = products_collection.count_documents({
            'seo_title': {'$exists': True},
            'seo_description': {'$exists': True},
            'seo_keywords': {'$exists': True},
            'seo_slug': {'$exists': True}
        })

        print(f"Total products: {total_products}")
        print(f"Products with SEO: {products_with_seo}")

    except Exception as e:
        print(f"Error during migration: {str(e)}")
        sys.exit(1)
    finally:
        if 'client' in locals():
            client.close()


if __name__ == "__main__":
    print("Starting SEO migration for products...")
    migrate_products()
