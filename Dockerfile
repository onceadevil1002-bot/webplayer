# Use Playwright official base image (includes Chromium + deps)
# ✅ Playwright official base image (with Python 3.10 + Chromium preinstalled)
FROM mcr.microsoft.com/playwright/python:v1.55.0-jammy

# Avoid pip warnings
ENV PIP_ROOT_USER_ACTION=ignore

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Playwright needs browsers (Chromium) installed
RUN playwright install --with-deps chromium

# Expose port
EXPOSE 8000

# Run FastAPI via Uvicorn
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]