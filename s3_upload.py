import boto3
import os
from dotenv import load_dotenv

load_dotenv()

def enviar_para_s3(filepath: str, key: str):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")

    # Validar credenciais AWS
    aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
    aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
    aws_region = os.getenv("AWS_REGION", "us-east-1")

    if not aws_access_key or not aws_secret_key:
        raise ValueError(
            "Credenciais AWS não encontradas. Configure AWS_ACCESS_KEY_ID e "
            "AWS_SECRET_ACCESS_KEY no arquivo .env"
        )

    bucket = os.getenv("AWS_S3_BUCKET", "chatvolt-peritho-bucket")

    s3 = boto3.client(
        "s3",
        aws_access_key_id=aws_access_key,
        aws_secret_access_key=aws_secret_key,
        region_name=aws_region
    )
    s3.upload_file(filepath, bucket, key)

    return f"s3://{bucket}/{key}"

