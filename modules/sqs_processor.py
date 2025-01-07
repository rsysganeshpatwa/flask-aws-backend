from threading import Thread
import json
import logging
from .aws_config import sqs_client
from .video_processor import process_task
from .config import SQS_QUEUE_URL  # Ensure the SQS_QUEUE_URL is defined in a central config file

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def start_sqs_processing(socketio):
    """
    Starts a thread to continuously process tasks from the SQS queue.
    """
    def process_tasks():
        logging.info("SQS processing thread started.")
        while True:
            try:
                # Receive a message from the SQS queue
                response = sqs_client.receive_message(
                    QueueUrl=SQS_QUEUE_URL,
                    MaxNumberOfMessages=1,
                    WaitTimeSeconds=10,
                )
                messages = response.get("Messages", [])
                if not messages:
                    continue

                for message in messages:
                    try:
                        body = json.loads(message["Body"])
                        logging.info(f"Received task: {body}")
                        process_task(body["task_id"], body["bucket"], body["key"], socketio)
                        
                        # Delete the processed message from the queue
                        sqs_client.delete_message(
                            QueueUrl=SQS_QUEUE_URL,
                            ReceiptHandle=message["ReceiptHandle"]
                        )
                        logging.info(f"Task {body['task_id']} completed and deleted from the queue.")

                    except Exception as task_error:
                        logging.error(f"Error processing task: {task_error}", exc_info=True)
            
            except Exception as sqs_error:
                logging.error(f"Error receiving messages from SQS: {sqs_error}", exc_info=True)

    # Start the SQS processing thread
    Thread(target=process_tasks, daemon=True).start()
    logging.info("SQS processing thread initialized.")
