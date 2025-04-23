FROM python:3.10

# Set the working directory to /app
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port (this is not required for a Telegram bot, but you can leave it for completeness)
EXPOSE 8000

# Run the bot application
CMD ["python", "main.py"]
