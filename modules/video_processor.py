# modules/video_processor.py
import cv2
import uuid
from .aws_config import s3_client, dynamo_table

YOLO_WEIGHTS = "yolov5s.pt"
YOLO_CONFIDENCE_THRESHOLD = 0.5

def process_task(task_id, bucket, key, socketio):
    local_file = f"/tmp/{key.split('/')[-1]}"
    processed_file = f"/tmp/processed_{key.split('/')[-1]}"
    s3_client.download_file(bucket, key, local_file)

    update_progress(task_id, 0, socketio)

    cap = cv2.VideoCapture(local_file)
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    out = cv2.VideoWriter(processed_file, cv2.VideoWriter_fourcc(*'mp4v'), 30, (frame_width, frame_height))

    model = cv2.dnn.readNet(YOLO_WEIGHTS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    processed_frames = 0

    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        blob = cv2.dnn.blobFromImage(frame, 1 / 255.0, (416, 416), swapRB=True, crop=False)
        model.setInput(blob)
        outputs = model.forward()

        for detection in outputs:
            confidence = detection[5]
            if confidence > YOLO_CONFIDENCE_THRESHOLD:
                x, y, w, h = map(int, detection[:4] * [frame_width, frame_height, frame_width, frame_height])
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        out.write(frame)
        processed_frames += 1
        progress = int((processed_frames / total_frames) * 100)
        update_progress(task_id, progress, socketio)

    cap.release()
    out.release()

    processed_key = f"processed/{uuid.uuid4()}.mp4"
    s3_client.upload_file(processed_file, bucket, processed_key)

    dynamo_table.update_item(
        Key={"task_id": task_id},
        UpdateExpression="SET status = :s, progress = :p, result_key = :rk",
        ExpressionAttributeValues={":s": "Complete", ":p": 100, ":rk": processed_key},
    )
    socketio.emit("progress", {"taskId": task_id, "progress": 100, "status": "Complete"})

def update_progress(task_id, progress, socketio):
    dynamo_table.update_item(
        Key={"task_id": task_id},
        UpdateExpression="SET progress = :p",
        ExpressionAttributeValues={":p": progress},
    )
    socketio.emit("progress", {"taskId": task_id, "progress": progress})

