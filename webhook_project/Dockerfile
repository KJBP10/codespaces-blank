FROM python:3.11-slim

# Install Redis client tools
RUN apt-get update && apt-get install -y redis-tools

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "webhook_project.wsgi:application"]