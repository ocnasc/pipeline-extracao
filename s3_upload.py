import boto3
import logging
import mimetypes
import os
from pathlib import Path
from typing import Optional

from botocore.exceptions import BotoCoreError, ClientError
from dotenv import load_dotenv


logger = logging.getLogger(__name__)
load_dotenv()


def _get_bucket_name(explicit_bucket: Optional[str] = None) -> str:
    """Resolve the target S3 bucket from argument or environment.

    Order of precedence: explicit argument > ENV AWS_S3_BUCKET > default constant.
    """
    if explicit_bucket:
        return explicit_bucket
    env_bucket = os.getenv("AWS_S3_BUCKET")
    if env_bucket:
        return env_bucket
    # Fallback to previous hardcoded bucket for backward compatibility
    return "chatvolt-peritho-bucket"


def _guess_content_type(filepath: Path) -> str:
    content_type, _ = mimetypes.guess_type(str(filepath))
    return content_type or "application/octet-stream"


def enviar_para_s3(filepath: str, key: str, bucket: Optional[str] = None) -> str:
    """Upload a local file to S3.

    Args:
        filepath: Path to the local file to upload
        key: Destination object key (path/name in the bucket)
        bucket: Optional bucket override; if not provided, uses AWS_S3_BUCKET env

    Returns:
        s3 URI string in the form s3://bucket/key
    """
    if not key or not isinstance(key, str):
        raise ValueError("Parâmetro 'key' inválido")

    src = Path(filepath)
    if not src.exists():
        raise FileNotFoundError(f"Arquivo não encontrado: {src}")
    if not src.is_file():
        raise ValueError(f"Caminho não é um arquivo: {src}")
    if not os.access(src, os.R_OK):
        raise PermissionError(f"Sem permissão de leitura: {src}")

    target_bucket = _get_bucket_name(bucket)
    content_type = _guess_content_type(src)

    try:
        s3 = boto3.client("s3")
        extra_args = {"ContentType": content_type}
        logger.info(f"Enviando arquivo para S3 | bucket={target_bucket} key={key} type={content_type}")
        s3.upload_file(str(src), target_bucket, key, ExtraArgs=extra_args)
        uri = f"s3://{target_bucket}/{key}"
        logger.info(f"Upload concluído: {uri}")
        return uri
    except (ClientError, BotoCoreError) as e:
        logger.error(f"Erro ao enviar para S3: {e}")
        raise

