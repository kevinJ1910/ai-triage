#!/bin/sh
# Genera un certificado autofirmado si no se monto uno real en /etc/nginx/certs.
# Para produccion, montar fullchain.pem y privkey.pem emitidos por una CA (p. ej. Let's Encrypt).
set -eu

CERT_DIR=/etc/nginx/certs
CERT="$CERT_DIR/fullchain.pem"
KEY="$CERT_DIR/privkey.pem"
SERVER_NAME="${TLS_SERVER_NAME:-localhost}"

if [ -s "$CERT" ] && [ -s "$KEY" ]; then
    echo "TLS: usando el certificado existente en $CERT_DIR"
    exit 0
fi

mkdir -p "$CERT_DIR"
openssl req -x509 -nodes -newkey rsa:2048 -days 825 \
    -keyout "$KEY" -out "$CERT" \
    -subj "/CN=$SERVER_NAME" \
    -addext "subjectAltName=DNS:$SERVER_NAME,DNS:localhost,IP:127.0.0.1" >/dev/null 2>&1
chmod 600 "$KEY"
echo "TLS: certificado autofirmado generado para $SERVER_NAME (el navegador mostrara una advertencia)"
