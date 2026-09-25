# Build context = RAIZ do repositorio, nao backend/.
# O backend importa de src/ (COST_ESTIMATE_RATE, as regras de segmentacao RFM
# e o gerador sintetico), entao os dois diretorios precisam ir junto.
# No Render: Root Directory = raiz do repo, Dockerfile Path = backend/Dockerfile.
FROM python:3.11-slim

WORKDIR /app

# requirements primeiro, sozinho: enquanto ele nao mudar, o Docker reaproveita
# a camada de pip install em vez de reinstalar tudo a cada commit de codigo.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

COPY src /app/src
COPY backend /app/backend

# O Render injeta a porta em $PORT. Fixar 10000 funciona por coincidencia (e o
# default deles) mas quebra se mudarem — entao respeitamos a variavel, com
# fallback pro uso local. Forma shell do CMD e necessaria pra expandir $PORT.
ENV PORT=10000
CMD python -m uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}
