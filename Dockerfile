FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY coder/ /app/coder/
COPY public/data/mms-2026-01.json /app/public/data/mms-2026-01.json
COPY public/data/dev_notes.jsonl /app/public/data/dev_notes.jsonl
RUN mkdir -p /in /out
ENTRYPOINT ["python", "-m", "coder"]
