import subprocess
import os

def convert_video_to_browser_friendly(input_file):
    """
    Converts a video to a browser-friendly format using FFmpeg.

    Parameters:
        input_file (str): Path to the input video file.

    Returns:
        str: Path to the converted video file.
    """
    # Define the temporary output file
    output_file = f"{os.path.splitext(input_file)[0]}_temp.mp4"

    # FFmpeg command for conversion
    ffmpeg_command = [
        'ffmpeg', '-i', input_file,
        '-movflags', 'faststart',  # Ensures proper metadata for streaming
        '-c:v', 'libx264',         # Convert to H.264 codec
        '-preset', 'slow',         # Encoding preset for quality vs speed
        '-crf', '22',              # Quality factor (lower = better quality)
        '-c:a', 'copy',            # Copy audio if present
        output_file
    ]

    try:
        # Run the FFmpeg command
        subprocess.run(ffmpeg_command, check=True)
        print(f"Video successfully converted to browser-friendly format: {output_file}")

        # Replace the original file with the converted one
        os.replace(output_file, input_file)
        print(f"Replaced original file with converted file: {input_file}")
        return input_file

    except FileNotFoundError:
        raise FileNotFoundError("FFmpeg is not installed. Please install it to ensure browser compatibility.")
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"FFmpeg processing failed: {e}")
