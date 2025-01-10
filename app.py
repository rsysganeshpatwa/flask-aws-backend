from flask import Flask, request, jsonify
from flask_socketio import SocketIO,emit
from flask_cors import CORS
from modules.aws_config import s3_client, dynamo_table
from modules.websocket_processor import start_task_processing  # Updated module
import uuid
import logging


# Flask app initialization
app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")

# Constants
S3_BUCKET = "logo-detection-bucket"  # Replace with your actual bucket name


# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

 # Initialize WebSocket-based task processing
start_task_processing(socketio)

@app.route("/get-presigned-url", methods=["POST"])
def get_presigned_url():
    """
    Generates a pre-signed URL for uploading files to S3.
    """
    try:
        data = request.json
        file_name = data.get("fileName")
        if not file_name:
            return jsonify({"error": "Missing 'fileName' in request"}), 400
        
        task_id = uuid.uuid4()
        key = f"{task_id}/input/{uuid.uuid4()}_{file_name}"
        url = s3_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=3600,
        )

        logging.info(f"Generated pre-signed URL for file: {key}")
        return jsonify({"url": url, "bucket": S3_BUCKET, "key": key})

    except Exception as e:
        logging.error(f"Error generating pre-signed URL: {e}", exc_info=True)
        return jsonify({"error": "Failed to generate pre-signed URL"}), 500


@app.route("/start-task", methods=["POST"])
def start_task():
    """
    Initiates a video processing task and updates DynamoDB with task metadata.
    """
    try:
        data = request.json
        bucket = data.get("bucket")
        key = data.get("key")
        if not bucket or not key:
            return jsonify({"error": "Missing 'bucket' or 'key' in request"}), 400
        
        task_id = str(key).split("/")[0]  # Use the key prefix as the task ID

        # # Add metadata to DynamoDB
        # dynamo_table.put_item(
        #     Item={
        #         "task_id": task_id,
        #         "status": "Pending",
        #         "progress": 0,
        #         "bucket": bucket,
        #         "key": key,
        #     }
        # )
        logging.info(f"Task metadata added to DynamoDB: TaskID={task_id}")

        # Notify frontend via WebSocket
         # Log before emitting
        logging.info(f"Emitting task event for task {task_id} to WebSocket...")

        socketio.emit("task", {"task_id": task_id, "bucket": bucket, "key": key})
    
        logging.info(f"Task {task_id} sent to WebSocket for processing.")

        return jsonify({"taskId": task_id})

    except Exception as e:
        logging.error(f"Error starting task: {e}", exc_info=True)
        return jsonify({"error": "Failed to start task"}), 500


if __name__ == "__main__":
    logging.info("Starting Flask app...")
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
