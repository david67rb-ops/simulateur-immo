# Image portable pour un hébergement web (Render, Railway, Fly.io, VPS...).
# Build : docker build -t simulateur-immo .
# Run   : docker run -p 8080:8080 -e PORT=8080 simulateur-immo
FROM python:3.12-slim

WORKDIR /app

# libgomp1 requis par pyarrow ; le reste couvre les dépendances de compilation
# pour les paquets sans wheel préconstruite sur certaines plateformes.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

COPY app/ ./app/
COPY gui/ ./gui/
COPY main.py .

# Cache des données de marché (DVF, loyers) téléchargées à la demande ;
# recréé si le volume n'est pas persistant sur l'hébergeur choisi.
RUN mkdir -p /app/app/data_cache

ENV PYTHONUNBUFFERED=1
EXPOSE 8080

CMD ["python3", "main.py", "--web"]
