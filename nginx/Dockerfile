FROM nginx:alpine

RUN apk add --no-cache openssl

# La imagen oficial procesa /etc/nginx/templates/*.template con envsubst hacia /etc/nginx/conf.d/
# y ejecuta los scripts de /docker-entrypoint.d/ antes de arrancar nginx.
ENV HSTS_MAX_AGE=0 \
    TLS_SERVER_NAME=localhost

COPY templates/ /etc/nginx/templates/
COPY 10-generate-self-signed-cert.sh /docker-entrypoint.d/
RUN rm -f /etc/nginx/conf.d/default.conf \
    && sed -i 's/\r$//' /docker-entrypoint.d/10-generate-self-signed-cert.sh /etc/nginx/templates/*.template \
    && chmod +x /docker-entrypoint.d/10-generate-self-signed-cert.sh

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
