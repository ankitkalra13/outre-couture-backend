#!/usr/bin/env python3
"""
One-time backup of existing DB collections to S3.

Collections:
  products, categories, media_pages, rfq_requests, users

Usage:
  python backup_existing_data.py
  python backup_existing_data.py --collection products
  python backup_existing_data.py --file ../outre_couture.products.json --collection products
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
for env_name in ('env.development', '.env', 'env.production'):
    env_path = ROOT / env_name
    if env_path.exists():
        load_dotenv(env_path)
        break
else:
    load_dotenv()

from backup_utils import backup_documents  # noqa: E402

ALL_COLLECTIONS = (
    'products',
    'categories',
    'media_pages',
    'rfq_requests',
    'users',
)


def load_collection_from_mongo(collection_name: str) -> list:
    from pymongo import MongoClient

    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        raise ValueError('MONGO_URI is required')

    db_name = os.getenv('DB_NAME', 'outre_couture')
    client = MongoClient(mongo_uri)
    docs = list(client[db_name][collection_name].find({}))
    client.close()
    return docs


def load_from_file(file_path: str) -> list:
    path = Path(file_path).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f'File not found: {path}')
    with path.open('r', encoding='utf-8') as fh:
        data = json.load(fh)
    if not isinstance(data, list):
        raise ValueError('JSON file must contain an array')
    return data


def main():
    parser = argparse.ArgumentParser(description='Backup existing Mongo collections to S3')
    parser.add_argument('--collection', choices=ALL_COLLECTIONS, help='Backup only one collection')
    parser.add_argument('--file', help='Optional JSON export (only with --collection)')
    args = parser.parse_args()

    if not os.getenv('AWS_S3_BUCKET') or not os.getenv('AWS_ACCESS_KEY_ID'):
        print('❌ AWS S3 env vars missing')
        sys.exit(1)

    if args.file and not args.collection:
        print('❌ --file requires --collection')
        sys.exit(1)

    collections = [args.collection] if args.collection else list(ALL_COLLECTIONS)
    any_failed = False

    for name in collections:
        try:
            if args.file:
                print(f'Loading {name} from file: {args.file}')
                docs = load_from_file(args.file)
            else:
                print(f'Loading {name} from MongoDB...')
                docs = load_collection_from_mongo(name)
        except Exception as exc:
            print(f'❌ Failed to load {name}: {exc}')
            any_failed = True
            continue

        print(f'Found {len(docs)} {name}. Uploading...')
        result = backup_documents(name, docs)
        print(
            f"  ✅ {name}: success={result['success']} failed={result['failed']} total={result['total']}"
        )
        if result['failed']:
            any_failed = True

    print('S3 path: backups/db/{collection}/{YYYY}/{MonthName}/{id}.json')
    if any_failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
