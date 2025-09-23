#!/usr/bin/env bash
set -o errexit

# Update system packages
apt-get update

# Install Playwright system dependencies explicitly
apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libgbm1 \
    libxss1 \
    libasound2 \
    libatspi2.0-0 \
    libgtk-3-0 \
    libgdk-pixbuf2.0-0

# Install Python requirements
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright with system deps
playwright install --with-deps chromium

# Verify installation
playwright install-deps chromium