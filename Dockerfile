FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY edicom_score ./edicom_score
ENV EDICOM_STORE_DIR=/data/store
EXPOSE 8000
# Mount a volume with the store built by `edicom-score build` on /data/store
CMD ["uvicorn", "edicom_score.api:app", "--host", "0.0.0.0", "--port", "8000"]
