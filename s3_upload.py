import boto3
import os

def enviar_para_s3(filepath: str, key: str):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Arquivo não encontrado: {filepath}")

    bucket = "chatvolt-peritho-bucket"
    s3 = boto3.client("s3")
    s3.upload_file(filepath, bucket, key)

    return f"s3://{bucket}/{key}"

