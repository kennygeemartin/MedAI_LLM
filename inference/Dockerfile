FROM pytorch/pytorch:2.6.0-cuda12.4-cudnn9-runtime
WORKDIR /app
COPY inference/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY inference ./inference
RUN useradd --create-home appuser
USER appuser
ENV HF_HOME=/home/appuser/.cache/huggingface
EXPOSE 8001
CMD ["uvicorn", "inference.main:app", "--host", "0.0.0.0", "--port", "8001", "--workers", "1"]
