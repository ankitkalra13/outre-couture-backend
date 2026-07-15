#!/usr/bin/env python3
"""
One-time backup of all existing products to S3.

Usage:
  # From MongoDB (preferred)
  python backup_existing_products.py

  # From exported JSON file
  python backup_existing_products.py --file ../outre_couture.products.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Load env before importing backup utils / pymongo client config
ROOT = Path(__file__).resolve().parent
for env_name in ('env.development', '.env', 'env.production'):
    env_path = ROOT / env_name
    if env_path.exists():
        load_dotenv(env_path)
        break
else:
    load_dotenv()

from backup_utils import backup_documents  # noqa: E402


def load_from_mongo():
    from pymongo import MongoClient

    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        raise ValueError('MONGO_URI is required to load products from MongoDB')

    db_name = os.getenv('DB_NAME', 'outre_couture')
    client = MongoClient(mongo_uri)
    products = list(client[db_name]['products'].find({}))
    client.close()
    return products


def load_from_file(file_path: str):
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f'File not found: {path}')

    with path.open('r', encoding='utf-8') as fh:
        data = json.load(fh)

    if not isinstance(data, list):
        raise ValueError('JSON file must contain an array of products')
    return data


def main():
    parser = argparse.ArgumentParser(description='Backup existing products to S3')
    parser.add_argument(
        '--file',
        help='Optional path to exported products JSON (Mongo extended JSON OK)',
    )
    args = parser.parse_args()

    if not os.getenv('AWS_S3_BUCKET') or not os.getenv('AWS_ACCESS_KEY_ID'):
        print('❌ AWS S3 env vars missing (AWS_S3_BUCKET / AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY)')
        sys.exit(1)

    try:
        if args.file:
            print(f'Loading products from file: {args.file}')
            products = load_from_file(args.file)
        else:
            print('Loading products from MongoDB...')
            products = load_from_mongo()
    except Exception as exc:
        print(f'❌ Failed to load products: {exc}')
        sys.exit(1)

    print(f'Found {len(products)} products. Uploading backups to S3...')
    result = backup_documents('products', products)
    print(
        f"✅ Done. success={result['success']} failed={result['failed']} total={result['total']}"
    )
    print('S3 path pattern: backups/db/products/YYYY/MonthName/DD/{product-id}.json')
    print('Example: backups/db/products/2026/July/15/{product-id}.json')

    if result['failed']:
        sys.exit(1)


if __name__ == '__main__':
    main()
