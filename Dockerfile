FROM python:3.13-slim

# Install system dependencies required for Playwright Chromium
RUN apt-get update && apt-get install -y \
    wget gnupg ca-certificates fonts-liberation \
    libasound2 libatk1.0-0 libcups2 libdbus-1-3 \
    libgdk-pixbuf2.0-0 libnspr4 libnss3 libx11-6 \
    libx11-xcb1 libxcb1 libxcomposite1 libxdamage1 \
    libxext6 libxfixes3 libxrandr2 libxrender1 \
    libxss1 libxtst6 xdg-utils && \
    rm -rf /var/lib/apt/lists/*

# Install Python requirements
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright + Chromium
RUN playwright install --with-deps chromium

# Copy project
COPY . .

# Run app
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]