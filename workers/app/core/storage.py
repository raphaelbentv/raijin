import uuid
from datetime import datetime
from functools import lru_cache
from io import BytesIO

import boto3
from botocore.client import Config

from app.core.config import get_settings


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


def download_object(key: str) -> bytes:
    settings = get_settings()
    client = _s3_client()
    buffer = BytesIO()
    client.download_fileobj(settings.s3_bucket_invoices, key, buffer)
    return buffer.getvalue()


def put_object(
    *, key: str, body: bytes, content_type: str, metadata: dict[str, str] | None = None
) -> None:
    settings = get_settings()
    _s3_client().put_object(
        Bucket=settings.s3_bucket_invoices,
        Key=key,
        Body=body,
        ContentType=content_type,
        Metadata=metadata or {},
    )


def build_object_key(tenant_id: uuid.UUID, filename: str) -> str:
    now = datetime.utcnow()
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"tenants/{tenant_id}/invoices/{now:%Y/%m}/{uuid.uuid4()}.{ext}"
