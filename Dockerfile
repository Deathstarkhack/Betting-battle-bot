# Use official Python base image
FROM python:3.10-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bot source code
COPY . .

# Set environment variables for Koyeb or your deployment platform to inject BOT_TOKEN and MONGO_URI
# You don't need to hardcode them

# Run the bot
CMD ["python", "main.py"]
