"""Servidor de conversão (consumidor): converte imagens para tons de cinza.

Vários conversores consomem a MESMA fila (competing consumers): o RabbitMQ
distribui as imagens entre eles. Após converter, a imagem é publicada no
exchange fanout, que entrega uma cópia a cada servidor de armazenamento.
"""
import io
import logging
import os
import socket

import pika
from PIL import Image

from common import GRAYSCALE_EXCHANGE, IMAGES_QUEUE, connect, declare_topology

CONVERTER_ID = os.getenv("CONVERTER_ID", socket.gethostname())
log = logging.getLogger(f"conversor-{CONVERTER_ID}")


def to_grayscale(data: bytes) -> bytes:
    """Converte para escala de cinza mantendo o formato original do arquivo."""
    with Image.open(io.BytesIO(data)) as img:
        fmt = img.format or "PNG"
        # "LA" preserva transparência de PNGs; demais viram "L" (8 bits, 1 canal)
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        gray = img.convert("LA" if has_alpha and fmt != "JPEG" else "L")
        out = io.BytesIO()
        gray.save(out, format=fmt)
        return out.getvalue()


def main() -> None:
    connection = connect()
    channel = connection.channel()
    declare_topology(channel)
    # Só pega a próxima imagem depois de terminar a atual: divide a carga
    # de forma justa entre os conversores
    channel.basic_qos(prefetch_count=1)

    def on_message(ch, method, properties, body):
        headers = properties.headers or {}
        filename = headers.get("filename", "sem_nome.png")
        try:
            gray = to_grayscale(body)
        except Exception as exc:  # imagem corrompida/formato inválido
            log.error("Falha ao converter %s: %s (descartada)", filename, exc)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            return

        ch.basic_publish(
            exchange=GRAYSCALE_EXCHANGE,
            routing_key="",
            body=gray,
            properties=pika.BasicProperties(
                delivery_mode=pika.DeliveryMode.Persistent,
                headers={**headers, "converted_by": CONVERTER_ID},
            ),
        )
        # ACK só depois de publicar: se o conversor cair no meio,
        # o RabbitMQ reentrega a imagem para outro conversor
        ch.basic_ack(delivery_tag=method.delivery_tag)
        log.info("Convertida: %s (%d -> %d bytes)", filename, len(body), len(gray))

    channel.basic_consume(queue=IMAGES_QUEUE, on_message_callback=on_message)
    log.info("Aguardando imagens na fila '%s'...", IMAGES_QUEUE)
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        channel.stop_consuming()
    connection.close()


if __name__ == "__main__":
    main()
