# Use the official Python image from the Docker Hub
FROM python:3.9-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire application to the container
COPY . .

# Expose the port the app will run on (default Flask port is 5000)
EXPOSE 5000

# Set the environment variable to disable buffering of the logs
ENV PYTHONUNBUFFERED 1

# Run the Flask application
CMD ["python", "app.py"]

