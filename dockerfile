# Use an official Python runtime as a parent image
FROM python:3.7
# Set working directory in container
WORKDIR /app
# Install system dependencies including git and ffmpeg
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
# Clone the repository
RUN git clone https://github.com/rsysganeshpatwa/flask-aws-backend.git .
# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
# Make port 5000 available to the world outside this container
EXPOSE 5000
# Run the application
CMD ["python3", "app.py"]