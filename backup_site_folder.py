#!/usr/bin/env python3
"""
One-time / manual backup of existing S3 folders into backups/assets/.

Default backs up the site/ folder:
  site/home-page/x.webp
    -> backups/assets/2026/July/site/home-page/x.webp

Usage:
  python backup_site_folder.py
  python backup_site_folder.py --prefix site/
  python backup_site_folder.py --prefix products/
"""

from __future__ import annotations

import argparse
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

from backup_utils import backup_s3_prefix  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description='Backup an S3 folder into backups/assets/')
    parser.add_argument(
        '--prefix',
        default='site/',
        help='S3 prefix to backup (default: site/)',
    )
    args = parser.parse_args()

    if not os.getenv('AWS_S3_BUCKET') or not os.getenv('AWS_ACCESS_KEY_ID'):
        print('❌ AWS S3 env vars missing')
        sys.exit(1)

    prefix = args.prefix if args.prefix.endswith('/') else f'{args.prefix}/'
    print(f'Backing up s3://{os.getenv("AWS_S3_BUCKET")}/{prefix} ...')
    result = backup_s3_prefix(prefix)
    if result.get('error'):
        print(f'❌ {result["error"]}')
        sys.exit(1)

    print(
        f"✅ Done. success={result['success']} failed={result['failed']} total={result['total']}"
    )
    print(
        f'Backup path pattern: backups/assets/YYYY/MonthName/{prefix}...'
    )
    if result['failed']:
        sys.exit(1)


if __name__ == '__main__':
    main()
