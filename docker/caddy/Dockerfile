# Caddy con el módulo de DuckDNS, para obtener certificados de Let's Encrypt
# mediante el reto DNS (sin exponer nada a internet).
ARG CADDY_VERSION=2.11

FROM caddy:${CADDY_VERSION}-builder AS builder
RUN xcaddy build --with github.com/caddy-dns/duckdns@v0.5.0

FROM caddy:${CADDY_VERSION}
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
COPY Caddyfile /etc/caddy/Caddyfile
