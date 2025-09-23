# Use Playwright official base image (includes Chromium + deps)
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

# Set work directory
WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy rest of the project
COPY . .

# Expose Render port
EXPOSE 8000

# Start with uvicorn (Chromium needs --no-sandbox)
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]