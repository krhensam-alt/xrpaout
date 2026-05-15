FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
ENV PYTHONUNBUFFERED=1
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "13151"]
