"""
Instant DB entry backups to S3 only.

Path:
  backups/db/{collection}/{YYYY}/{MM}/{DD}/{doc_id}.json
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
    """Make Mongo/BSON values JSON-safe."""
    if isinstance(obj, dict):
        if set(obj.keys()) == {'$oid'}:
            return obj['$oid']
        if set(obj.keys()) == {'$date'}:
            return obj['$date']
        return {k: serialize_for_backup(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_for_backup(item) for item in obj]
    if isinstance(obj, ObjectId):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def _document_id(document: dict) -> str:
    if document.get('id'):
        return str(document['id'])
    raw_id = document.get('_id')
    if isinstance(raw_id, dict) and '$oid' in raw_id:
        return str(raw_id['$oid'])
    if raw_id is not None:
        return str(raw_id)
    return datetime.utcnow().strftime('%Y%m%d%H%M%S%f')


def backup_document(collection_name: str, document: dict) -> bool:
    """
    Backup one DB document to S3.
    Never raises — returns True on success, False if skipped/failed.
    """
    try:
        s3_client = _get_s3_client()
        bucket = os.getenv('AWS_S3_BUCKET')
        if not s3_client or not bucket:
            logger.warning('DB backup skipped: AWS S3 is not configured')
            return False

        safe_doc = serialize_for_backup(document)
        doc_id = _document_id(safe_doc if isinstance(safe_doc, dict) else document)
        now = datetime.utcnow()
        key = (
            f"backups/db/{collection_name}/"
            f"{now.strftime('%Y')}/{now.strftime('%B')}/{now.strftime('%d')}/"
            f"{doc_id}.json"
        )

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
