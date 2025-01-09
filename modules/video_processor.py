import cv2
import csv
import os
import uuid
import logging
from ultralytics import YOLO
import boto3
from .aws_config import s3_client, dynamo_table
import tempfile

# Load the trained YOLO model
model = YOLO("modules/trained_module/best.pt")

# Constants
YOLO_CONFIDENCE_THRESHOLD = 0.5
OUTPUT_BUCKET = "logo-detection-bucket"  # Update with your output bucket name

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def process_task(task_id, input_bucket, input_key, socketio):
    """
    Processes a video task: downloads the video and model from S3, applies object detection,
    uploads the processed video to S3, and updates the task's status in DynamoDB.
    """
    try:
        # File paths (use temp directory for processing)
        local_file = tempfile.mktemp(suffix=".mp4")
        processed_video_file = tempfile.mktemp(suffix="_processed.mp4")
        report_file = tempfile.mktemp(suffix="_report.csv")

        # Step 1: Download video from S3
        logging.info(f"Downloading video from S3: Bucket={input_bucket}, Key={input_key}")
        s3_client.download_file(input_bucket, input_key, local_file)
        logging.info(f"Video downloaded to {local_file}")
        update_progress(task_id, 0, socketio)

        # Step 2: Process video frame by frame
        cap = cv2.VideoCapture(local_file)
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(cap.get(cv2.CAP_PROP_FPS))
        frame_time = 1 / fps
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        processed_frames = 0

        out = cv2.VideoWriter(processed_video_file, cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width, frame_height))
        occurrences = {}  # {track_id: {start_frame, start_time, end_frame, end_time, duration, clip_path}}
        total_count = 0

        logging.info(f"Video processing initialized. Total frames: {total_frames}")

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            current_frame = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
            current_time = current_frame * frame_time

            # Run YOLO tracking on the frame
            results = model.track(frame, persist=True)

            if results[0].boxes.data is not None and results[0].boxes.id is not None:
                boxes = results[0].boxes.xyxy.cpu()
                track_ids = results[0].boxes.id.int().cpu().tolist()
                class_indices = results[0].boxes.cls.int().cpu().tolist()
                conflist = results[0].boxes.conf.cpu().tolist()

                for box, track_id, classidx, conf in zip(boxes, track_ids, class_indices, conflist):
                    x1, y1, x2, y2 = map(int, box)
                    classname = model.names[classidx]

                    # Draw rectangle and track ID
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"id: {track_id} : {classname}, conf:{conf:.2f}", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                    if track_id not in occurrences:
                        # New track ID: Start tracking
                        total_count += 1
                        occurrences[track_id] = {
                            "start_frame": current_frame,
                            "start_time": current_time,
                            "end_frame": None,
                            "end_time": None,
                            "duration": None,
                            "clip_path": None,
                            "confidences": [conf],
                            "classname": classname
                        }
                    else:
                        # Update the end frame and time
                        occurrences[track_id]["end_frame"] = current_frame
                        occurrences[track_id]["end_time"] = current_time
                        occurrences[track_id]["duration"] = (
                                occurrences[track_id]["end_time"] - occurrences[track_id]["start_time"]
                        )
                        occurrences[track_id]["confidences"].append(conf)
                        occurrences[track_id]["classname"] = classname

            # Add total count overlay on the frame
            cv2.putText(frame, f"Total Count: {total_count}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

            # Write processed frame to output video
            out.write(frame)

            # Update progress
            processed_frames += 1
            progress = int((processed_frames / total_frames) * 100)
            update_progress(task_id, progress, socketio)

        cap.release()
        out.release()
        logging.info(f"Video processing completed. Processed file: {processed_video_file}")

        # Step 3: Create a unique folder and upload processed files to S3
        unique_folder = str(uuid.uuid4())  # Create a unique folder for the task
        processed_key = f"{unique_folder}/processed_video.mp4"
        report_key = f"{unique_folder}/track_report.csv"

        logging.info(f"Uploading processed video to S3: Bucket={OUTPUT_BUCKET}, Key={processed_key}")
        s3_client.upload_file(processed_video_file, OUTPUT_BUCKET, processed_key)
        logging.info(f"Processed video uploaded to {processed_key}")

        # Step 4: Save the tracking report
        logging.info(f"Uploading tracking report to S3: Bucket={OUTPUT_BUCKET}, Key={report_key}")
        with open(report_file, mode="w", newline="") as report:
            csv_writer = csv.writer(report)
            csv_writer.writerow(["Count", "Track ID", "Video Time", "Visible Duration", "FPS", "Clip File", "Classname", "Avg Confidence"])

            for track_id, data in occurrences.items():
                if data["duration"] is not None and data["duration"] > 0:
                    avg_confidence = sum(data["confidences"]) / len(data["confidences"])
                    video_time = f"{data['start_time']:.2f}-{data['end_time']:.2f}"
                    csv_writer.writerow([track_id, video_time, f"{data['duration']:.2f} seconds", fps, data["clip_path"], data["classname"], f"{avg_confidence:.2f}"])

        # Upload report
        s3_client.upload_file(report_file, OUTPUT_BUCKET, report_key)
        logging.info(f"Tracking report uploaded to {report_key}")

        # Step 5: Update task status in DynamoDB
        dynamo_table.update_item(
            Key={"task_id": task_id},
            UpdateExpression="SET status = :s, progress = :p, result_key = :rk",
            ExpressionAttributeValues={":s": "Complete", ":p": 100, ":rk": processed_key},
        )
        logging.info(f"Task {task_id} marked as complete in DynamoDB.")

        # Emit WebSocket event
        socketio.emit("progress", {"taskId": task_id, "progress": 100, "status": "Complete"})

    except Exception as e:
        logging.error(f"Error processing task {task_id}: {e}", exc_info=True)
        socketio.emit("progress", {"taskId": task_id, "progress": 0, "status": "Error", "message": str(e)})

def update_progress(task_id, progress, socketio):
    """
    Updates the progress of the task in DynamoDB and emits a WebSocket event.
    """
    try:
        # Update progress in DynamoDB
        dynamo_table.update_item(
            Key={"task_id": task_id},
            UpdateExpression="SET progress = :p",
            ExpressionAttributeValues={":p": progress},
        )
        # Emit progress update to WebSocket
        socketio.emit("progress", {"taskId": task_id, "progress": progress})
        logging.info(f"Task {task_id} progress updated to {progress}%.")

    except Exception as e:
        logging.error(f"Error updating progress for task {task_id}: {e}", exc_info=True)
