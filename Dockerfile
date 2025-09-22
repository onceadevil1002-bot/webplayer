FROM python:3.11-slim

WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt

# install playwright browsers
RUN playwright install --with-deps

EXPOSE 8000
CMD ["python", "server.py"]
