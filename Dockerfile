# Use Playwright official base image (includes Chromium + deps)
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway injects PORT, default to 8000 if not set
ENV PORT=8000

CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port $PORT"]