#!/usr/bin/env bash
set -o errexit

# Install all requirements
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright Chromium + required system deps
playwright install --with-deps chromium