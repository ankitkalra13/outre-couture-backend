#!/usr/bin/env python3
"""
Manually remove orphan product images from S3.

An image is orphan if it lives under products/ and is not referenced
by any product document in MongoDB (deleted products / replaced images).

Safe default is dry-run.

Usage:
  # Preview
  python cleanup_orphan_product_images.py

  # Delete orphans older than 30 days
  python cleanup_orphan_product_images.py --older-than-days 30 --apply

  # Delete all orphans now
  python cleanup_orphan_product_images.py --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
for env_name in ('env.development', '.env', 'env.production'):
    env_path = ROOT / env_name
    if env_path.exists():
        load_dotenv(env_path)
        break
else:
    load_dotenv()

import boto3
from boto3.session import Config
from pymongo import MongoClient


def get_s3_client():
    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    bucket = os.getenv('AWS_S3_BUCKET')
    region = os.getenv('AWS_REGION', 'ap-south-1')
    if not access_key or not secret_key or not bucket:
        return None, None
    client = boto3.client(
        's3',
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4'),
    )
    return client, bucket


def extract_key_from_url(image_url: str) -> str | None:
    if not image_url or not isinstance(image_url, str):
        return None

    cdn = (os.getenv('AWS_CDN_BASE_URL') or '').rstrip('/')
    bucket = os.getenv('AWS_S3_BUCKET')
    region = os.getenv('AWS_REGION', 'ap-south-1')

    if cdn and image_url.startswith(f'{cdn}/'):
        return image_url[len(cdn) + 1:]

    if bucket:
        bucket_host = f'{bucket}.s3.{region}.amazonaws.com'
        if image_url.startswith(f'https://{bucket_host}/'):
            return image_url[len(f'https://{bucket_host}/'):]

    # Generic https URL — use path without leading slash
    parsed = urlparse(image_url)
    if parsed.scheme in ('http', 'https') and parsed.path:
        return parsed.path.lstrip('/')

    return None


def referenced_product_keys() -> set[str]:
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        raise ValueError('MONGO_URI is required')

    db_name = os.getenv('DB_NAME', 'outre_couture')
    client = MongoClient(mongo_uri)
    keys = set()
    for product in client[db_name]['products'].find({}, {'images': 1, '_id': 0}):
        for url in product.get('images') or []:
            key = extract_key_from_url(url)
            if key:
                keys.add(key)
    client.close()
    return keys


def list_product_image_objects(s3, bucket: str) -> list[dict]:
    objects = []
    continuation = None
    while True:
        kwargs = {'Bucket': bucket, 'Prefix': 'products/'}
        if continuation:
            kwargs['ContinuationToken'] = continuation
        response = s3.list_objects_v2(**kwargs)
        for item in response.get('Contents') or []:
            key = item['Key']
            if key.endswith('/'):
                continue
            objects.append({
                'key': key,
                'last_modified': item.get('LastModified'),
                'size': item.get('Size', 0),
            })
        if not response.get('IsTruncated'):
            break
        continuation = response.get('NextContinuationToken')
    return objects


def main():
    parser = argparse.ArgumentParser(
        description='Clean orphan product images from S3'
    )
    parser.add_argument(
        '--older-than-days',
        type=int,
        default=0,
        help='Only remove orphans last-modified at least N days ago (0 = any age)',
    )
    parser.add_argument(
        '--apply',
        action='store_true',
        help='Actually delete. Without this flag, dry-run only.',
    )
    args = parser.parse_args()

    s3, bucket = get_s3_client()
    if not s3 or not bucket:
        print('❌ AWS S3 env vars missing')
        sys.exit(1)

    cutoff = None
    if args.older_than_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.older_than_days)

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'Mode: {mode}')
    if cutoff:
        print(f'Only orphans older than {args.older_than_days} days')
    print()

    try:
        live_keys = referenced_product_keys()
    except Exception as exc:
        print(f'❌ Failed loading product image refs from MongoDB: {exc}')
        sys.exit(1)

    try:
        s3_objects = list_product_image_objects(s3, bucket)
    except Exception as exc:
        print(f'❌ Failed listing S3 products/ prefix (needs s3:ListBucket on products/): {exc}')
        sys.exit(1)

    orphans = []
    for item in s3_objects:
        if item['key'] in live_keys:
            continue
        if cutoff and item.get('last_modified'):
            modified = item['last_modified']
            if modified.tzinfo is None:
                modified = modified.replace(tzinfo=timezone.utc)
            if modified > cutoff:
                continue
        orphans.append(item)

    print(f'Images referenced by live products: {len(live_keys)}')
    print(f'Images under s3://{bucket}/products/: {len(s3_objects)}')
    print(f'Orphans to remove: {len(orphans)}')
    print()

    for item in orphans:
        print(f"  - {item['key']}")
        if args.apply:
            s3.delete_object(Bucket=bucket, Key=item['key'])

    print()
    if args.apply:
        print(f'✅ Deleted {len(orphans)} orphan product image(s).')
    else:
        print(f'Dry-run complete. {len(orphans)} orphan image(s) would be deleted.')
        print('Re-run with --apply to delete them.')


if __name__ == '__main__':
    main()
