# Use Python 3.11, as was originally intended
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file first to leverage Docker's caching
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# --- ADD THESE LINES ---
# Explicitly copy the directories needed by your application
COPY ./templates ./templates
COPY ./static ./static

# Copy the rest of the application files
COPY main.py .
COPY .env .

# Expose the port your application will run on
EXPOSE 10000

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]