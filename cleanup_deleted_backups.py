#!/usr/bin/env python3
"""
Manually remove S3 backups for records that no longer exist in MongoDB.

Safe default is dry-run (shows what would be deleted).

Usage:
  # Preview orphan backups (no delete)
  python cleanup_deleted_backups.py

  # Actually delete orphan backups
  python cleanup_deleted_backups.py --apply

  # Only one collection
  python cleanup_deleted_backups.py --collection products --apply

  # Only orphans older than N days
  python cleanup_deleted_backups.py --older-than-days 30 --apply
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone
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

from backup_utils import list_backup_keys  # noqa: E402
from pymongo import MongoClient  # noqa: E402

ALL_COLLECTIONS = (
    'products',
    'categories',
    'media_pages',
    'rfq_requests',
    'users',
)


def live_ids(collection_name: str) -> set[str]:
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        raise ValueError('MONGO_URI is required')

    db_name = os.getenv('DB_NAME', 'outre_couture')
    client = MongoClient(mongo_uri)
    collection = client[db_name][collection_name]
    ids = set()

    for doc in collection.find({}, {'id': 1, '_id': 1}):
        if doc.get('id'):
            ids.add(str(doc['id']))
        if doc.get('_id') is not None:
            ids.add(str(doc['_id']))

    client.close()
    return ids


def main():
    parser = argparse.ArgumentParser(
        description='Clean S3 backups for deleted MongoDB records'
    )
    parser.add_argument(
        '--collection',
        choices=ALL_COLLECTIONS,
        help='Limit to one collection (default: all)',
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

    if not os.getenv('AWS_S3_BUCKET') or not os.getenv('AWS_ACCESS_KEY_ID'):
        print('❌ AWS S3 env vars missing')
        sys.exit(1)

    collections = [args.collection] if args.collection else list(ALL_COLLECTIONS)
    cutoff = None
    if args.older_than_days > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=args.older_than_days)

    mode = 'APPLY' if args.apply else 'DRY-RUN'
    print(f'Mode: {mode}')
    print(f'Collections: {", ".join(collections)}')
    if cutoff:
        print(f'Only orphans older than {args.older_than_days} days')
    print()

    from backup_utils import _get_s3_client

    s3 = _get_s3_client()
    bucket = os.getenv('AWS_S3_BUCKET')
    if not s3 or not bucket:
        print('❌ S3 client not configured')
        sys.exit(1)

    total_found = 0
    total_deleted = 0

    for name in collections:
        print(f'--- {name} ---')
        try:
            mongo_ids = live_ids(name)
        except Exception as exc:
            print(f'  ❌ Failed loading Mongo IDs: {exc}')
            continue

        backups = list_backup_keys(name)
        orphans = []
        for item in backups:
            if item['doc_id'] in mongo_ids:
                continue
            if cutoff and item.get('last_modified'):
                modified = item['last_modified']
                if modified.tzinfo is None:
                    modified = modified.replace(tzinfo=timezone.utc)
                if modified > cutoff:
                    continue
            orphans.append(item)

        print(f'  Live in Mongo: {len(mongo_ids)}')
        print(f'  Backups in S3: {len(backups)}')
        print(f'  Orphans to remove: {len(orphans)}')

        for item in orphans:
            total_found += 1
            print(f"  - {item['key']}")
            if args.apply:
                s3.delete_object(Bucket=bucket, Key=item['key'])
                total_deleted += 1

        print()

    if args.apply:
        print(f'✅ Deleted {total_deleted} orphan backup file(s).')
    else:
        print(f'Dry-run complete. {total_found} orphan file(s) would be deleted.')
        print('Re-run with --apply to delete them.')


if __name__ == '__main__':
    main()
