from flask import Flask, jsonify
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import time

app = Flask(__name__)
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*")


# Handle the 'task' event and emit progress updates
@socketio.on("task")
def handle_task(data):
    task_id = data.get("taskId")
    print(f"Task started: {task_id}")

    # Simulate task processing and emit progress updates
    for progress in range(0, 101, 10):
        emit("task", {"taskId": task_id, "progress": progress})
        socketio.sleep(1)  # Simulate processing delay (1 second)
    print(f"Task {task_id} completed!")

@socketio.on("connect")
def test_connect():
    print("Client connected")


def test_connect():
    print("get connected")

# Simple endpoint to start the task (use this for client testing)
@app.route("/start-task", methods=["GET"])
def start_task():
    task_id = "12345"  # Use a fixed task ID for simplicity
    # Emit the initial progress to simulate task start
    success = socketio.emit("task", {"taskId": task_id, "progress": 0})
    print(f"sussess: {success}")
    return jsonify({"taskId": task_id})

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
