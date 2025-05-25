FROM python:3.11-slim

# Set working directory in container
WORKDIR /code

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code
COPY app ./app

#  Tạo thư mục log để middleware không lỗi FileNotFoundError
RUN mkdir -p /code/app/requests_log

ENV PYTHONUNBUFFERED=1
# Expose FastAPI port (optional, since NGINX will proxy)
EXPOSE 8000

# Launch the FastAPI app with Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]