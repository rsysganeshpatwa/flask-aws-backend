# get_module.py
from flask import Blueprint, jsonify, request
from ultralytics import YOLO
import os

# Blueprint for modular route handling
get_module_blueprint = Blueprint('get_module', __name__)

# Define the directory where your .pt files are located
MODULE_DIR = "modules/trained_module/"  # Change this to your actual directory

@get_module_blueprint.route("/get-modules", methods=["GET"])
def get_modules():
    """
    API endpoint to get the list of .pt files from the directory.
    """
    try:
        # Read the files in the specified directory
        files = os.listdir(MODULE_DIR)
        
        # Filter out files that are not .pt files
        pt_files = [file for file in files if file.endswith(".pt")]

        if not pt_files:
            return jsonify({"message": "No .pt files found"}), 404

        return jsonify({"modules": pt_files}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@get_module_blueprint.route("/get-classes", methods=["GET"])
def get_classes():
    """
    API endpoint to get class names for a particular .pt file.
    Expects a query parameter `filename` to specify the .pt file.
    """
    try:
        # Get the filename from the request arguments
        filename = request.args.get("filename")

        if not filename:
            return jsonify({"error": "No filename specified"}), 400

        # Check if the specified file exists in the directory
        pt_file_path = os.path.join(MODULE_DIR, filename)
        if not os.path.exists(pt_file_path):
            return jsonify({"error": "File not found"}), 404

        # Load the YOLO model
        model = YOLO(pt_file_path)
        
        # Get class names
        class_names = model.names
    
        if not class_names:
            return jsonify({"error": "No classes found for the model"}), 404

        return jsonify({"classes": class_names}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500