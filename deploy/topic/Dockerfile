FROM python:3.12-slim
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cpu
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/models/huggingface \
    TOPIC_METHOD=bertopic
WORKDIR /app
COPY backend/requirements.txt backend/requirements-topic-cloud.txt /tmp/
RUN pip install --no-cache-dir torch==2.14.0 --index-url ${TORCH_INDEX_URL} \
    && pip install --no-cache-dir -r /tmp/requirements-topic-cloud.txt \
    && useradd --create-home appuser && mkdir -p /models/huggingface && chown -R appuser /models
COPY backend/ /app/
RUN python -c "from pathlib import Path; p=Path('agents/topic/models/provisional_topic_model_v2.pkl'); assert p.is_file() and not p.open('rb').read(80).startswith(b'version https://git-lfs.github.com/spec/'), 'Restore the Git LFS model before building'"
USER appuser
EXPOSE 5000
# One worker avoids duplicating model memory.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "900", "app:app"]
