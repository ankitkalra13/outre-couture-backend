"""
Live DB backups to S3.

On create/update: writes/updates
  backups/db/{collection}/{YYYY}/{MonthName}/{doc_id}.json

On delete: JSON backup is KEPT (for recovery).
Run cleanup_deleted_backups.py manually when you want to remove
backups for records that no longer exist in MongoDB.

Required IAM:
  - s3:PutObject / s3:DeleteObject on bucket objects
  - s3:ListBucket (for cleanup script)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any

import boto3
from boto3.session import Config
from bson import ObjectId

logger = logging.getLogger(__name__)

_s3_client = None

SENSITIVE_FIELDS = {'password', 'hashed_password', 'password_hash'}


def _get_s3_client():
    global _s3_client
    if _s3_client is not None:
        return _s3_client

    access_key = os.getenv('AWS_ACCESS_KEY_ID')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
    bucket = os.getenv('AWS_S3_BUCKET')
    region = os.getenv('AWS_REGION', 'ap-south-1')

    if not access_key or not secret_key or not bucket:
        return None

    _s3_client = boto3.client(
        's3',
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version='s3v4'),
    )
    return _s3_client


def serialize_for_backup(obj: Any) -> Any:
    """Make Mongo/BSON values JSON-safe and strip secrets."""
    if isinstance(obj, dict):
        if set(obj.keys()) == {'$oid'}:
            return obj['$oid']
        if set(obj.keys()) == {'$date'}:
            return obj['$date']
        return {
            k: serialize_for_backup(v)
            for k, v in obj.items()
            if k not in SENSITIVE_FIELDS
        }
    if isinstance(obj, list):
        return [serialize_for_backup(item) for item in obj]
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def document_id(document: dict) -> str:
    if document.get('id'):
        return str(document['id'])
    raw_id = document.get('_id')
    if isinstance(raw_id, dict) and '$oid' in raw_id:
        return str(raw_id['$oid'])
    if raw_id is not None:
        return str(raw_id)
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def backup_key(collection_name: str, doc_id: str, when: datetime | None = None) -> str:
    when = when or datetime.utcnow()
    return (
        f"backups/db/{collection_name}/"
        f"{when.strftime('%Y')}/{when.strftime('%B')}/"
        f"{doc_id}.json"
    )


def list_backup_keys(collection_name: str | None = None) -> list[dict]:
    """
    List backup objects.
    Returns [{key, collection, doc_id, last_modified}, ...]
    """
    s3_client = _get_s3_client()
    bucket = os.getenv('AWS_S3_BUCKET')
    if not s3_client or not bucket:
        return []

    prefix = f"backups/db/{collection_name}/" if collection_name else "backups/db/"
    results = []
    continuation = None

    while True:
        kwargs = {'Bucket': bucket, 'Prefix': prefix}
        if continuation:
            kwargs['ContinuationToken'] = continuation
        response = s3_client.list_objects_v2(**kwargs)
        for item in response.get('Contents') or []:
            key = item['Key']
            if not key.endswith('.json'):
                continue
            parts = key.split('/')
            # backups/db/{collection}/{year}/{month}/{id}.json
            if len(parts) < 6:
                continue
            results.append({
                'key': key,
                'collection': parts[2],
                'doc_id': parts[-1][:-5],  # strip .json
                'last_modified': item.get('LastModified'),
                'size': item.get('Size', 0),
            })
        if not response.get('IsTruncated'):
            break
        continuation = response.get('NextContinuationToken')

    return results


def list_backup_keys_for_id(collection_name: str, doc_id: str) -> list[str]:
    suffix = f"/{doc_id}.json"
    return [
        item['key']
        for item in list_backup_keys(collection_name)
        if item['doc_id'] == str(doc_id) or item['key'].endswith(suffix)
    ]


def backup_document(collection_name: str, document: dict) -> bool:
    """
    Create/update one document backup in S3 for the current Year/Month.
    Does NOT delete older month copies (kept for restore safety).
    Never raises.
    """
    try:
        s3_client = _get_s3_client()
        bucket = os.getenv('AWS_S3_BUCKET')
        if not s3_client or not bucket:
            logger.warning('DB backup skipped: AWS S3 is not configured')
            return False

        safe_doc = serialize_for_backup(document)
        doc_id = document_id(safe_doc if isinstance(safe_doc, dict) else document)
        key = backup_key(collection_name, doc_id)
        body = json.dumps(safe_doc, ensure_ascii=False, indent=2).encode('utf-8')

        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=body,
            ContentType='application/json',
        )
        logger.info('Backed up %s/%s -> s3://%s/%s', collection_name, doc_id, bucket, key)
        return True
    except Exception as exc:
        logger.error('DB backup failed for %s: %s', collection_name, exc)
        return False


def delete_backup(collection_name: str, doc_id: str) -> bool:
    """Delete all S3 backup files for a document id. Never raises."""
    try:
        s3_client = _get_s3_client()
        bucket = os.getenv('AWS_S3_BUCKET')
        if not s3_client or not bucket:
            logger.warning('DB backup delete skipped: AWS S3 is not configured')
            return False

        keys = list_backup_keys_for_id(collection_name, str(doc_id))
        if not keys:
            logger.info('No backup found for %s/%s', collection_name, doc_id)
            return True

        for key in keys:
            s3_client.delete_object(Bucket=bucket, Key=key)
            logger.info('Deleted backup s3://%s/%s', bucket, key)
        return True
    except Exception as exc:
        logger.error('DB backup delete failed for %s/%s: %s', collection_name, doc_id, exc)
        return False


def backup_documents(collection_name: str, documents: list) -> dict:
    """Backup many documents. Returns counts."""
    ok = 0
    failed = 0
    for doc in documents:
        if backup_document(collection_name, doc):
            ok += 1
        else:
            failed += 1
    return {'success': ok, 'failed': failed, 'total': len(documents)}


def asset_backup_key(source_key: str, when: datetime | None = None) -> str:
    """Map a live asset key to its backup key."""
    when = when or datetime.utcnow()
    clean = (source_key or '').lstrip('/')
    return (
        f"backups/assets/"
        f"{when.strftime('%Y')}/{when.strftime('%B')}/"
        f"{clean}"
    )


def backup_s3_object(source_key: str) -> bool:
    """
    Copy a live S3 object into backups/assets/{Year}/{Month}/{source_key}.
    Used for site/ (and other upload folders). Never raises.
    """
    try:
        s3_client = _get_s3_client()
        bucket = os.getenv('AWS_S3_BUCKET')
        if not s3_client or not bucket:
            logger.warning('Asset backup skipped: AWS S3 is not configured')
            return False

        source_key = (source_key or '').lstrip('/')
        if not source_key or '..' in source_key:
            logger.warning('Asset backup skipped: invalid key %s', source_key)
            return False

        dest_key = asset_backup_key(source_key)
        s3_client.copy_object(
            Bucket=bucket,
            CopySource={'Bucket': bucket, 'Key': source_key},
            Key=dest_key,
            MetadataDirective='COPY',
        )
        logger.info('Asset backed up %s -> s3://%s/%s', source_key, bucket, dest_key)
        return True
    except Exception as exc:
        logger.error('Asset backup failed for %s: %s', source_key, exc)
        return False


def backup_s3_prefix(prefix: str = 'site/') -> dict:
    """
    Copy all objects under a prefix into backups/assets/{Year}/{Month}/...
    Returns counts.
    """
    s3_client = _get_s3_client()
    bucket = os.getenv('AWS_S3_BUCKET')
    if not s3_client or not bucket:
        return {'success': 0, 'failed': 0, 'total': 0, 'error': 'S3 not configured'}

    prefix = prefix if prefix.endswith('/') else f'{prefix}/'
    ok = 0
    failed = 0
    total = 0
    continuation = None

    while True:
        kwargs = {'Bucket': bucket, 'Prefix': prefix}
        if continuation:
            kwargs['ContinuationToken'] = continuation
        response = s3_client.list_objects_v2(**kwargs)
        for item in response.get('Contents') or []:
            key = item['Key']
            if key.endswith('/'):
                continue
            total += 1
            if backup_s3_object(key):
                ok += 1
            else:
                failed += 1
        if not response.get('IsTruncated'):
            break
        continuation = response.get('NextContinuationToken')

    return {'success': ok, 'failed': failed, 'total': total}
