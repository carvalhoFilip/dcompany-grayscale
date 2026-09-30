"""Servidor de armazenamento: salva TODAS as imagens convertidas (redundância).

Cada servidor tem sua própria fila durável ligada ao exchange fanout,
então todos recebem uma cópia de cada imagem.
"""
import logging
import os
from pathlib import Path

from common import GRAYSCALE_EXCHANGE, connect, declare_topology

STORAGE_ID = os.getenv("STORAGE_ID", "1")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", f"data/servers/{STORAGE_ID}"))
QUEUE_NAME = f"storage_{STORAGE_ID}"

log = logging.getLogger(f"armazenamento-{STORAGE_ID}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    connection = connect()
    channel = connection.channel()
    declare_topology(channel)
    # Fila durável com nome fixo: se o servidor cair, as imagens ficam
    # guardadas no RabbitMQ até ele voltar
    channel.queue_declare(queue=QUEUE_NAME, durable=True)
    channel.queue_bind(queue=QUEUE_NAME, exchange=GRAYSCALE_EXCHANGE)
    channel.basic_qos(prefetch_count=10)

    def on_message(ch, method, properties, body):
        headers = properties.headers or {}
        # Path(...).name evita que um nome malicioso escreva fora da pasta
        filename = Path(headers.get("filename", "sem_nome.png")).name
        (OUTPUT_DIR / filename).write_bytes(body)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        log.info(
            "Salva: %s em %s (cliente %s, conversor %s)",
            filename, OUTPUT_DIR, headers.get("client_id", "?"), headers.get("converted_by", "?"),
        )

    channel.basic_consume(queue=QUEUE_NAME, on_message_callback=on_message)
    log.info("Aguardando imagens convertidas na fila '%s'...", QUEUE_NAME)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    connection.close()


if __name__ == "__main__":
    main()
