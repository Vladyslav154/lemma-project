# Use Python 3.11 as the base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy requirements file first to leverage Docker's cache
COPY requirements.txt .

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all project files into the working directory
COPY . .

# Expose the port the app will run on
EXPOSE 10000

# Command to run the application, specifying the 'src' module
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "10000"]