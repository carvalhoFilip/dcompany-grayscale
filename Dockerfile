FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

# Mostra os logs em tempo real no "docker compose logs"
ENV PYTHONUNBUFFERED=1

# O comando (client.py, converter.py ou storage.py) é definido no docker-compose
CMD ["python", "client.py"]
