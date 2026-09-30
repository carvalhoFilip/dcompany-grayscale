"""Configuração compartilhada entre clientes, conversores e armazenamento."""
import logging
import os
import time

import pika

RABBIT_HOST = os.getenv("RABBIT_HOST", "localhost")
RABBIT_USER = os.getenv("RABBIT_USER", "guest")
RABBIT_PASS = os.getenv("RABBIT_PASS", "guest")

# Fila de trabalho: produtores -> conversores (cada imagem vai para UM conversor)
IMAGES_QUEUE = "images"
# Exchange fanout: conversores -> TODOS os servidores de armazenamento
GRAYSCALE_EXCHANGE = "grayscale_images"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    datefmt="%H:%M:%S",
)
logging.getLogger("pika").setLevel(logging.WARNING)


def connect(retries: int = 30, delay: float = 2.0) -> pika.BlockingConnection:
    """Conecta ao RabbitMQ, tentando de novo enquanto o broker sobe."""
    params = pika.ConnectionParameters(
        host=RABBIT_HOST,
        credentials=pika.PlainCredentials(RABBIT_USER, RABBIT_PASS),
        heartbeat=600,
    )
    for attempt in range(1, retries + 1):
        try:
            return pika.BlockingConnection(params)
        except pika.exceptions.AMQPConnectionError:
            logging.getLogger("conn").info(
                "RabbitMQ indisponível (tentativa %d/%d), aguardando...", attempt, retries
            )
            time.sleep(delay)
    raise RuntimeError(f"Não foi possível conectar ao RabbitMQ em {RABBIT_HOST}")


def declare_topology(channel) -> None:
    """Declara fila e exchange (idempotente: todos os componentes podem chamar)."""
    channel.queue_declare(queue=IMAGES_QUEUE, durable=True)
    channel.exchange_declare(exchange=GRAYSCALE_EXCHANGE, exchange_type="fanout", durable=True)
