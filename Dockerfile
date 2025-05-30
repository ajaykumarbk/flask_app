# # Use the official Python image from the Docker Hub
# FROM python:3.9-slim

# # Set the working directory inside the container
# WORKDIR /app

# # Copy the requirements file and install dependencies
# COPY requirements.txt .

# RUN pip install --no-cache-dir -r requirements.txt

# # Copy the entire application to the container
# COPY . .

# # Expose the port the app will run on (default Flask port is 5000)
# EXPOSE 5000

# # Set the environment variable to disable buffering of the logs
# ENV PYTHONUNBUFFERED 1

# # Run the Flask application
# CMD ["python", "app.py"]

# Stage 1: Base Image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Create a non-root user
RUN adduser --disabled-password --no-create-home appuser

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . .

# Change to the non-root user
USER appuser

# Expose the Flask port
EXPOSE 5000

# Use Gunicorn to run the app in production
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
