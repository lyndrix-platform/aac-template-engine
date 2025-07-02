FROM python:3.9-slim

# Install git, which is not included in the slim image
RUN apt-get update && apt-get install -y git && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Copy the script and dependencies into the image
COPY scripts/ /app/scripts/
COPY requirements.txt /app/

# Install the dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt