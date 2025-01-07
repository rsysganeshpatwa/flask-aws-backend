from flask import Flask, request, jsonify
from flask_socketio import SocketIO
from flask_cors import CORS
from modules.aws_config import s3_client, sqs_client, dynamo_table
from modules.sqs_processor import start_sqs_processing
from modules.video_processor import process_task
import uuid
import json

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

@app.route("/get-presigned-url", methods=["POST"])
def get_presigned_url():
    data = request.json
    file_name = data["fileName"]
    key = f"uploads/{uuid.uuid4()}_{file_name}"

    url = s3_client.generate_presigned_url(
        "put_object",
        Params={"Bucket": S3_BUCKET, "Key": key},
        ExpiresIn=3600,
    )

    return jsonify({"url": url, "bucket": S3_BUCKET, "key": key})

@app.route("/start-task", methods=["POST"])
def start_task():
    data = request.json
    task_id = str(uuid.uuid4())

    # Add metadata to DynamoDB
    dynamo_table.put_item(
        Item={
            "task_id": task_id,
            "status": "Pending",
            "progress": 0,
            "bucket": data["bucket"],
            "key": data["key"],
        }
    )

    # Add the task to the SQS queue
    sqs_client.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps({"task_id": task_id, "bucket": data["bucket"], "key": data["key"]}),
    )

    return jsonify({"taskId": task_id})

if __name__ == "__main__":
    start_sqs_processing(socketio)
    socketio.run(app, host="0.0.0.0", port=5000)