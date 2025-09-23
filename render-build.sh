#!/usr/bin/env bash
set -o errexit

# Install all requirements
pip install --upgrade pip
pip install -r requirements.txt

# Install Playwright Chromium browser
playwright install chromium