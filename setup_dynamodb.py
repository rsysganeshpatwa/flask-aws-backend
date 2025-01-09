
# setup_dynamodb.py
import boto3
import os

AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DYNAMO_TABLE = os.getenv("DYNAMO_TABLE", "logo-detection-results")

dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)

def create_table():
    table = dynamodb.create_table(
        TableName=DYNAMO_TABLE,
        KeySchema=[
            {"AttributeName": "task_id", "KeyType": "HASH"}
        ],
        AttributeDefinitions=[
            {"AttributeName": "task_id", "AttributeType": "S"}
        ],
        ProvisionedThroughput={"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
    )
    table.wait_until_exists()
    print(f"Table {DYNAMO_TABLE} created successfully.")

if __name__ == "__main__":
    create_table()