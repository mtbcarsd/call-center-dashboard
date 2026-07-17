"""S3-совместимое хранилище аудио (Railway Bucket) — заливка записей из
pipeline.py и presigned-ссылки для плеера в dashboard.py.

Без AWS_* переменных модуль работает в отключённом режиме: upload_audio()
тихо ничего не делает, presigned_url() возвращает None — дашборд просто
не покажет плеер для звонков без аудио (или если хранилище не настроено).
"""
import os

import boto3
from botocore.config import Config
from dotenv import load_dotenv

load_dotenv()

_BUCKET = os.environ.get("AWS_S3_BUCKET_NAME")


def _client():
    if not _BUCKET:
        return None
    return boto3.client(
        "s3",
        endpoint_url=os.environ["AWS_ENDPOINT_URL"],
        aws_access_key_id=os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["AWS_SECRET_ACCESS_KEY"],
        region_name=os.environ.get("AWS_DEFAULT_REGION", "auto"),
        config=Config(signature_version="s3v4"),
    )


def upload_audio(file_path: str, key: str) -> str | None:
    """Заливает файл в бакет под key. Возвращает key при успехе, иначе None."""
    client = _client()
    if client is None:
        return None
    client.upload_file(file_path, _BUCKET, key)
    return key


def presigned_url(key: str | None, expires_sec: int = 3600) -> str | None:
    if not key:
        return None
    client = _client()
    if client is None:
        return None
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": _BUCKET, "Key": key},
        ExpiresIn=expires_sec,
    )
