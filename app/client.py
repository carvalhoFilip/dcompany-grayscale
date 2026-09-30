"""Cliente (produtor): lê as imagens da sua pasta e envia para a fila de imagens."""
import logging
import os
import sys
import time
from pathlib import Path

import pika

from common import IMAGE_EXTENSIONS, IMAGES_QUEUE, connect, declare_topology

CLIENT_ID = os.getenv("CLIENT_ID", "1")
INPUT_DIR = Path(os.getenv("INPUT_DIR", f"data/clients/{CLIENT_ID}"))
# Espera os servidores de armazenamento criarem suas filas antes de enviar
START_DELAY = float(os.getenv("START_DELAY", "0"))

log = logging.getLogger(f"cliente-{CLIENT_ID}")


def main() -> None:
    if not INPUT_DIR.is_dir():
        log.error("Pasta de entrada %s não existe", INPUT_DIR)
        sys.exit(1)

    images = sorted(
        p for p in INPUT_DIR.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS
    )
    if not images:
        log.warning("Nenhuma imagem encontrada em %s", INPUT_DIR)
        return

    if START_DELAY:
        time.sleep(START_DELAY)

    connection = connect()
    channel = connection.channel()
    declare_topology(channel)

    for image in images:
        channel.basic_publish(
            exchange="",
            routing_key=IMAGES_QUEUE,
            body=image.read_bytes(),
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
                headers={"filename": image.name, "client_id": CLIENT_ID},
            ),
        )
        log.info("Enviada: %s (%d bytes)", image.name, image.stat().st_size)

    log.info("Concluído: %d imagem(ns) enviada(s) de %s", len(images), INPUT_DIR)
    connection.close()


if __name__ == "__main__":
    main()
