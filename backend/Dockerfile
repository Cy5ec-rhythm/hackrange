# Start from a small official Python image
FROM python:3.12-slim

# All commands below run inside /app in the container
WORKDIR /app

# Copy dependency list first (so Docker can cache this layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy the actual application code
COPY app.py .
COPY orchestrator.py .

# Tell Docker this container listens on port 5000
EXPOSE 5000

# Command that runs when the container starts
CMD ["python", "app.py"]
