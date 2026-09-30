# DCompany – Conversão de imagens para tons de cinza com RabbitMQ

Atividade 01 U1 – Sistemas Distribuídos (COMP0470) – UFS

## Arquitetura

```
 Cliente 1 ─┐                        ┌─> Conversor 1 ─┐                 ┌─> fila storage_1 ─> Armazenamento 1
            ├─> fila "images" ───────┤                ├─> exchange  ────┤
 Cliente 2 ─┘   (work queue)         └─> Conversor N ─┘   fanout (X)    └─> fila storage_2 ─> Armazenamento 2
```

| Componente | Arquivo | Papel no RabbitMQ |
|---|---|---|
| Cliente (produtor) | `app/client.py` | Lê as imagens da sua pasta e publica na fila `images` |
| Servidor de conversão | `app/converter.py` | Consome da fila `images`, converte para cinza e publica no exchange `grayscale_images` |
| Servidor de armazenamento | `app/storage.py` | Tem sua própria fila ligada ao exchange e salva as imagens na sua pasta |

**Decisões de projeto**

- **Divisão de carga entre conversores:** todos consomem a mesma fila (*competing consumers*). Com `prefetch_count=1`, cada conversor só pega uma nova imagem quando termina a atual, então a carga é dividida de forma justa.
- **Redundância no armazenamento:** o exchange é do tipo `fanout`, que entrega uma cópia de cada mensagem para todas as filas ligadas a ele. Cada servidor de armazenamento tem sua fila (`storage_1`, `storage_2`, ...), então todos salvam todas as imagens.
- **Mesmo nome da imagem original:** o cliente envia o nome do arquivo no header da mensagem (`filename`), que é repassado pelo conversor até o armazenamento.
- **Nada se perde:** filas duráveis, mensagens persistentes e ACK manual. O conversor só confirma a mensagem depois de publicar a imagem convertida; se ele cair no meio, o RabbitMQ reentrega a imagem para outro conversor. Se um servidor de armazenamento cair, as imagens ficam na fila dele até ele voltar.
- **Formato preservado:** JPG continua JPG e PNG continua PNG (1 canal de cinza, o que reduz o tamanho do arquivo).

## Estrutura

```
.
├── app/
│   ├── common.py        # conexão com o RabbitMQ e declaração de fila/exchange
│   ├── client.py        # produtor
│   ├── converter.py     # conversor
│   └── storage.py       # armazenamento
├── data/
│   ├── clients/1/       # imagens enviadas pelo cliente 1
│   ├── clients/2/       # imagens enviadas pelo cliente 2
│   ├── servers/1/       # saída do armazenamento 1
│   └── servers/2/       # saída do armazenamento 2
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Como executar

Pré-requisito: Docker com Docker Compose.

```bash
docker build -t dcompany-grayscale .
docker compose up
```

A imagem é construída uma vez e reutilizada por todos os serviços. Vários serviços compartilham a tag `dcompany-grayscale`; usar `docker compose up --build` faz o Compose construí-los em paralelo e pode falhar com `image already exists`.

Isso sobe o RabbitMQ, 2 servidores de armazenamento, 2 conversores e 2 clientes. Os clientes enviam as imagens e encerram; os servidores continuam rodando aguardando novas imagens. Para parar: `Ctrl+C` e depois `docker compose down`.

## Como verificar o funcionamento

1. **Resultado:** as pastas `data/servers/1/` e `data/servers/2/` devem conter **todas** as 6 imagens dos dois clientes, em tons de cinza e com os mesmos nomes originais.
2. **Logs:** cada armazenamento mostra qual cliente enviou e qual conversor processou cada imagem, mostrando a carga dividida entre os conversores.
   ```bash
   docker compose logs converter storage1 storage2
   ```

## Testes adicionais

**Mais conversores (escalabilidade):**

```bash
docker build -t dcompany-grayscale .
docker compose up --scale converter=4
```

**Enviar as imagens novamente** (com o sistema rodando, em outro terminal):

```bash
docker compose run --rm client1
docker compose run --rm client2
```

**Tolerância a falha de um armazenamento:**

```bash
docker compose stop storage2
docker compose run --rm client1      # storage2 está fora: as imagens ficam na fila storage_2
docker compose start storage2        # ao voltar, storage2 recebe e salva as imagens pendentes
```

**Usar suas próprias imagens:** coloque arquivos `.jpg`, `.png`, `.bmp`, `.gif`, `.webp` ou `.tiff` em `data/clients/1/` ou `data/clients/2/` e rode de novo. Use nomes diferentes entre os clientes, já que arquivos com o mesmo nome se sobrescrevem no armazenamento.

**Limpar a saída:**

```bash
rm -f data/servers/1/*.* data/servers/2/*.*
```

## Executando sem Docker (opcional)

Com um RabbitMQ rodando em `localhost:5672` (ex.: `docker run -d -p 5672:5672 rabbitmq:3.13`):

```bash
pip install -r requirements.txt
cd app

# um terminal para cada processo
STORAGE_ID=1 OUTPUT_DIR=../data/servers/1 python storage.py
STORAGE_ID=2 OUTPUT_DIR=../data/servers/2 python storage.py
CONVERTER_ID=1 python converter.py
CONVERTER_ID=2 python converter.py

# por último, os clientes
CLIENT_ID=1 INPUT_DIR=../data/clients/1 python client.py
CLIENT_ID=2 INPUT_DIR=../data/clients/2 python client.py
```

## Variáveis de ambiente

| Variável | Usada por | Padrão |
|---|---|---|
| `RABBIT_HOST` | todos | `localhost` |
| `RABBIT_USER` / `RABBIT_PASS` | todos | `guest` / `guest` |
| `CLIENT_ID`, `INPUT_DIR` | cliente | `1`, `data/clients/<id>` |
| `START_DELAY` | cliente | `0` (segundos de espera antes de enviar) |
| `CONVERTER_ID` | conversor | hostname do container |
| `STORAGE_ID`, `OUTPUT_DIR` | armazenamento | `1`, `data/servers/<id>` |
