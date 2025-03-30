# Use an official Python runtime as a parent image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1 

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN apt-get update && apt-get install -y iputils-ping

# Copy requirements.txt and install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN pip install whitenoise
RUN apt-get update && apt-get install -y iputils-ping

# Copy the project code
COPY . /app/

# Collect static files
RUN python manage.py collectstatic --noinput

# Copy entrypoint script and ensure it's executable
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose the port for the web server
EXPOSE 8000

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]
