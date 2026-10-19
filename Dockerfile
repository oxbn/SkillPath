FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 SKILLPATH_CACHE_DIR=/data
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
COPY backend ./backend
COPY templates ./templates
COPY static ./static
RUN useradd --create-home skillpath && mkdir /data && chown skillpath:skillpath /data
USER skillpath
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
