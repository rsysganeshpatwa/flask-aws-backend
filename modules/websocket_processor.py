import json
import logging
from threading import Thread
from .video_processor import process_task  # Ensure `process_task` is implemented to handle tasks

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def start_task_processing(socketio):
    """
    Starts WebSocket-based task processing.
    """
    logging.info("Initializing WebSocket task processing...")
    def handle_task(data,socketio):
        """
        Handles a task received via WebSocket.
        """
        try:
            # Parse task details
            task_id = data.get("taskId")
            bucket = data.get("bucket")
            key = data.get("key")

            logging.info(f"Processing task: {task_id} {bucket} {key}")
        

            if not (task_id and bucket and key):
                logging.warning(f"Incomplete task data received: {data}")
                return

            logging.info(f"Processing task: {data}")
            process_task(task_id, bucket, key, socketio)
            logging.info(f"Task {task_id} completed.")

        except Exception as e:
            logging.error(f"Error processing task: {e}", exc_info=True)

    def setup_websocket_listener():
        """
        Listens for WebSocket events and processes tasks.
        """
        @socketio.on("task")
        def on_task(data):
           logging.info(f"Task received via WebSocket: {data}")
           #handle_task(data,socketio)
           #Thread(target=handle_task, args=(data,socketio,), daemon=True).start()
           socketio.start_background_task(target=handle_task, data=data, socketio=socketio)

           

            
        @socketio.on("connect")
        def handle_connect():
           logging.info("WebSocket client connected")
        
        @socketio.on("progress")
        def progress(data):
           logging.info(f"Progress: {data}")
        
       

    setup_websocket_listener()
    logging.info("WebSocket task processing initialized.")
