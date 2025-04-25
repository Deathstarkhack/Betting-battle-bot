# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set environment variables
ENV BOT_TOKEN=your_bot_token
ENV MONGO_URI=your_mongo_uri

# Set working directory
WORKDIR /app

# Copy bot files into the container
COPY . /app

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Command to run the bot
CMD ["python", "main.py"]
