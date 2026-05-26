FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt uvicorn

COPY api/ ./api/
COPY lib/ ./lib/
COPY db/ ./db/

ENV PYTHONPATH=/app

EXPOSE 8000

CMD ["uvicorn", "api.index:app", "--host", "0.0.0.0", "--port", "8000"]
