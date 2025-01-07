# modules/aws_config.py
import boto3
import os

AWS_REGION = os.getenv("AWS_REGION", "<your-region>")
S3_BUCKET = os.getenv("S3_BUCKET", "<your-s3-bucket>")
DYNAMO_TABLE = os.getenv("DYNAMO_TABLE", "<your-dynamodb-table>")
SQS_QUEUE_URL = os.getenv("SQS_QUEUE_URL", "<your-sqs-queue-url>")

s3_client = boto3.client("s3", region_name=AWS_REGION)
sqs_client = boto3.client("sqs", region_name=AWS_REGION)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
dynamo_table = dynamodb.Table(DYNAMO_TABLE)