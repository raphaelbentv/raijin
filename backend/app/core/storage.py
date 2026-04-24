import uuid
from datetime import datetime
from functools import lru_cache
from typing import BinaryIO

import boto3
from botocore.client import Config

from app.core.config import get_settings


class StorageError(Exception):
    pass


@lru_cache
def _s3_client():
    settings = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


@lru_cache
def _s3_signing_client():
    """Client dédié aux URLs signées — utilise S3_PUBLIC_URL si défini.

    En dev Docker, le backend atteint MinIO via http://minio:9000 (réseau interne)
    mais le navigateur ne peut pas résoudre ce hostname. On signe donc avec
    http://localhost:6900 pour que les URLs soient cliquables côté client.
    En prod avec S3/Azure Blob public, S3_PUBLIC_URL = S3_ENDPOINT_URL.
    """
    settings = get_settings()
    public_url = settings.s3_public_url or settings.s3_endpoint_url
    return boto3.client(
        "s3",
        endpoint_url=public_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket() -> None:
    settings = get_settings()
    client = _s3_client()
    try:
        client.head_bucket(Bucket=settings.s3_bucket_invoices)
    except Exception:
        client.create_bucket(Bucket=settings.s3_bucket_invoices)


def build_object_key(tenant_id: uuid.UUID, filename: str) -> str:
    now = datetime.utcnow()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"tenants/{tenant_id}/invoices/{now:%Y/%m}/{uuid.uuid4()}.{ext}"


def put_object(
    *,
    key: str,
    body: BinaryIO | bytes,
    content_type: str,
    metadata: dict[str, str] | None = None,
) -> None:
    settings = get_settings()
    client = _s3_client()
    client.put_object(
        Bucket=settings.s3_bucket_invoices,
        Key=key,
        Body=body,
        ContentType=content_type,
        Metadata=metadata or {},
    )


def generate_presigned_url(key: str, *, expires_in: int | None = None) -> str:
    settings = get_settings()
    client = _s3_signing_client()
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": settings.s3_bucket_invoices, "Key": key},
        ExpiresIn=expires_in or settings.s3_signed_url_ttl_seconds,
    )


def delete_object(key: str) -> None:
    settings = get_settings()
    client = _s3_client()
    client.delete_object(Bucket=settings.s3_bucket_invoices, Key=key)
