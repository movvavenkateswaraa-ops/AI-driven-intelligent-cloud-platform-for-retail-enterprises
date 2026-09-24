FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PORT=8080
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8080
# Single worker keeps the demo SQLite file safe; scale out by moving to a managed database.
CMD ["sh", "-c", "gunicorn -w 1 --threads 4 -b 0.0.0.0:${PORT} app:app"]
