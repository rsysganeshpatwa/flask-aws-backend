import cv2
import csv
import os
import uuid
import logging
from ultralytics import YOLO
import boto3
from .aws_config import s3_client, dynamo_table
import tempfile
from mimetypes import guess_type  # Import guess_type from mimetypes
from .ffmpeg_postprocess import convert_video_to_browser_friendly




# Constants
YOLO_CONFIDENCE_THRESHOLD = 0.5
OUTPUT_BUCKET = "logo-detection-bucket"  # Update with your output bucket name

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")



def process_task(task_id, input_bucket, input_key, socketio, module_name, class_names):
    try:
        # Load the trained YOLO model
        model = YOLO(f"modules/trained_module/{module_name}")
        # File paths (use temp directory for processing)
        local_file = tempfile.mktemp(suffix=".mp4")
        processed_video_file = tempfile.mktemp(suffix="_processed.mp4")
        report_file = tempfile.mktemp(suffix="_report.csv")
        clip_folder = tempfile.mkdtemp()  # Folder for saving clips

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
        occurrences = {}
        total_count = 0

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
                print('classname',class_names)

                for box, track_id, classidx, conf in zip(boxes, track_ids, class_indices, conflist):
                    x1, y1, x2, y2 = map(int, box)
                    classname = model.names[classidx]

                    # Filter by class names
                    print('classname',class_names)
                    if classname not in class_names:
                        continue

                    # Draw rectangle and track ID
                    cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                    cv2.putText(frame, f"id: {track_id} : {classname}, conf:{conf:.2f}", (x1, y1 - 10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)

                    if track_id not in occurrences:
                        total_count += 1
                        clip_path = os.path.join(clip_folder, f"{track_id}.mp4")
                        clip_out = cv2.VideoWriter(clip_path, cv2.VideoWriter_fourcc(*'mp4v'), fps, (frame_width, frame_height))
                        occurrences[track_id] = {
                            "start_frame": current_frame,
                            "start_time": current_time,
                            "end_frame": None,
                            "end_time": None,
                            "duration": None,
                            "clip_path": clip_path,
                            "clip_out": clip_out,
                            "confidences": [conf],
                            "classname": classname
                        }
                    else:
                        occurrences[track_id]["end_frame"] = current_frame
                        occurrences[track_id]["end_time"] = current_time
                        occurrences[track_id]["duration"] = (
                                occurrences[track_id]["end_time"] - occurrences[track_id]["start_time"]
                        )
                        occurrences[track_id]["confidences"].append(conf)
                        occurrences[track_id]["classname"] = classname
                        
                    occurrences[track_id]["clip_out"].write(frame)

            cv2.putText(frame, f"Total Count: {total_count}", (10, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            out.write(frame)
            processed_frames += 1
            progress = int((processed_frames / total_frames) * 100)
            update_progress(task_id, progress, socketio)

        # Close video files
        cap.release()
        out.release()
        for occ in occurrences.values():
            occ["clip_out"].release()

        unique_folder = str(task_id)


        processed_video_file = convert_video_to_browser_friendly(processed_video_file)
          # Guess the MIME type of the file (fallback to 'binary/octet-stream')
        mime_type, _ = guess_type(processed_video_file)
        mime_type = mime_type or "binary/octet-stream"
        # Upload clips and generate pre-signed URLs
        for track_id, data in occurrences.items():
            if data["clip_path"]:
                clip_key = f"{unique_folder}/output/clips/{track_id}.mp4"
                data["clip_path"] = convert_video_to_browser_friendly(data["clip_path"])
                s3_client.upload_file(data["clip_path"], OUTPUT_BUCKET, clip_key,ExtraArgs={"ContentType": mime_type})
                #data["clip_url"] = s3_client.generate_presigned_url('get_object', Params={'Bucket': OUTPUT_BUCKET, 'Key': clip_key}, ExpiresIn=3600)

        # Generate pre-signed URL for processed video
      

        processed_key = f"{unique_folder}/output/processed_video.mp4"
        s3_client.upload_file(processed_video_file, OUTPUT_BUCKET, processed_key, ExtraArgs={"ContentType": mime_type})
        processed_video_url = s3_client.generate_presigned_url('get_object', Params={'Bucket': OUTPUT_BUCKET, 'Key': processed_key,'ResponseContentType': 'video/mp4','ResponseContentDisposition': 'inline'}, ExpiresIn=3600)

        # Generate and upload report
        with open(report_file, mode="w", newline="") as report:
            csv_writer = csv.writer(report)
            csv_writer.writerow(["SR.", "Start Time", "End Time", "Duration", "Object Name", "Avg Confidence"])
            for track_id, data in occurrences.items():
                if data["duration"]:
                    avg_conf = sum(data["confidences"]) / len(data["confidences"])
                    csv_writer.writerow([
                        track_id, 
                        f"{data['start_time']:.2f}",  # Format start_time to 2 decimal places
                        f"{data['end_time']:.2f}",    # Format end_time to 2 decimal places
                        f"{data['duration']:.2f}",    # Format duration to 2 decimal places
                        data["classname"], 
                        f"{avg_conf:.2f}"
                    ])
        report_key = f"{unique_folder}/output/report.csv"
        s3_client.upload_file(report_file, OUTPUT_BUCKET, report_key)
        report_url = s3_client.generate_presigned_url('get_object', Params={'Bucket': OUTPUT_BUCKET, 'Key': report_key}, ExpiresIn=3600)

        # Emit results to WebSocket
        socketio.emit("progress", {
            "taskId": task_id,
            "progress": 100,
            "status": "Complete",
            "videoUrl": processed_video_url,
            "reportUrl": report_url,
            "summary": [{"trackId": track_id, "classname": data["classname"]} for track_id, data in occurrences.items()]
        })
    except Exception as e:
        logging.error(f"Error processing task {task_id}: {e}", exc_info=True)
        socketio.emit("progress", {"taskId": task_id, "progress": 0, "status": "Error", "message": str(e)})

def update_progress(task_id, progress, socketio):
    """
    Updates the progress of the task in DynamoDB and emits a WebSocket event.
    """
    try:
         # Emit progress update to WebSocket
       
        socketio.emit("progress", {"taskId": task_id, "progress": progress})
        socketio.sleep(0.1)  # Allow time for the progress event to be sent
        # # Update progress in DynamoDB
        # dynamo_table.update_item(
        #     Key={"task_id": task_id},
        #     UpdateExpression="SET progress = :p",
        #     ExpressionAttributeValues={":p": progress},
        # )
       
        logging.info(f"Task {task_id} progress updated to {progress}%.")

    except Exception as e:
        logging.error(f"Error updating progress for task {task_id}: {e}", exc_info=True)
