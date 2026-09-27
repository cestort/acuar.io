# Despliegue en el VPS

La app se despliega sola con GitHub Actions en cada push a `main`: primero pasan los tests y después se sube el código al VPS por SSH y se levantan los contenedores con `docker compose`.

```
push a main ──► Tests ──► SSH al VPS ──► docker compose up --build ──► espera a /health/
```

En el VPS corren estos contenedores, con los puertos publicados **solo en la IP de WireGuard**:

| Servicio | Puerto | Para qué |
|---|---|---|
| `app` (Django + gunicorn) | `WG_BIND_IP:7733` | La aplicación (HTTP directo) |
| `ntfy` | `WG_BIND_IP:7734` | Notificaciones de alertas (HTTP directo) |
| `caddy` (opcional) | `WG_BIND_IP:443` y `:8443` | HTTPS para la app y ntfy |

Los datos (SQLite, caché de ntfy y certificados) están en volúmenes de Docker, así que un despliegue nunca los borra.

## 1. Preparar el VPS (una sola vez)

Requisitos: Ubuntu con Docker, el plugin `docker compose` y WireGuard funcionando.

Entra en el VPS con tu usuario habitual y ejecuta:

```bash
curl -fsSLO https://raw.githubusercontent.com/cestort/acuar.io/main/scripts/setup-vps.sh
sudo bash setup-vps.sh
```

El script:

- crea el usuario `deploy` (sin contraseña) con acceso a Docker;
- crea `/opt/acuario`;
- genera una clave SSH exclusiva para GitHub Actions (limitada con `restrict`: sin reenvío de puertos ni terminal interactiva);
- hace que Docker arranque después de WireGuard, para que tras un reinicio los contenedores puedan usar la IP de la VPN;
- comprueba que los puertos 7733, 7734, 443 y 8443 estén libres (si alguno está ocupado, cámbialo con las variables del paso 2);
- muestra al final todos los valores que hay que guardar en GitHub.

Se puede volver a ejecutar sin problema: sustituye la clave de GitHub Actions por una nueva.

Opciones, por si tu configuración es distinta:

```bash
sudo WG_IFACE=wg1 PUBLIC_HOST=mi-vps.ejemplo.com DEPLOY_PATH=/srv/acuario bash setup-vps.sh
```

## 2. Guardar secretos y variables en GitHub

En el repositorio: **Settings → Secrets and variables → Actions**.

**Secrets** (pestaña *Secrets*):

| Nombre | Valor |
|---|---|
| `VPS_HOST` | IP o dominio público del VPS |
| `VPS_USER` | `deploy` |
| `VPS_SSH_KEY` | Clave privada que muestra el script (con las líneas `BEGIN`/`END`) |
| `VPS_SSH_KNOWN_HOSTS` | Líneas de huella del servidor que muestra el script |
| `DJANGO_SECRET_KEY` | Clave aleatoria que genera el script |
| `OPENROUTER_API_KEY` | Tu clave de OpenRouter (opcional hasta que exista el chat) |
| `DUCKDNS_TOKEN` | Token de tu cuenta de DuckDNS (solo si activas HTTPS) |

**Variables** (pestaña *Variables*):

| Nombre | Obligatoria | Valor |
|---|---|---|
| `WG_BIND_IP` | Sí | IP del VPS dentro de la VPN, p. ej. `10.8.0.1` |
| `VPS_SSH_PORT` | No | Puerto SSH si no es el 22 |
| `DEPLOY_PATH` | No | Directorio de la app si no es `/opt/acuario` |
| `APP_PORT` | No | Puerto de la app (por defecto `7733`) |
| `NTFY_PORT` | No | Puerto de ntfy (por defecto `7734`) |
| `BIND_IP` | No | IP donde se publican los puertos (por defecto, `WG_BIND_IP`). Con `0.0.0.0` quedan abiertos a internet: Docker se salta UFW |
| `APP_DOMAIN` | No | Subdominio de DuckDNS, p. ej. `acuario-esteve-macon.duckdns.org`. Al definirlo se activa HTTPS |
| `HTTPS_PORT` | No | Puerto HTTPS de la app (por defecto `443`) |
| `NTFY_HTTPS_PORT` | No | Puerto HTTPS de ntfy (por defecto `8443`) |

Mientras `WG_BIND_IP` no exista, el workflow solo ejecuta los tests y se salta el despliegue.

## 3. Desplegar

Cualquier push a `main` despliega. Para lanzar el primer despliegue sin hacer cambios: **Actions → CI/CD → Run workflow**.

Tras el despliegue, desde el móvil con la VPN conectada:

| | Con HTTPS (`APP_DOMAIN` definido) | Sin HTTPS |
|---|---|---|
| App | `https://APP_DOMAIN` | `http://WG_BIND_IP:7733` |
| ntfy (app **ntfy** de Android, añadir servidor) | `https://APP_DOMAIN:8443` | `http://WG_BIND_IP:7734` |

En el cliente WireGuard del móvil, `AllowedIPs` debe incluir la IP del VPS en la VPN (p. ej. `10.8.0.1/32` o toda la subred).

## 4. HTTPS con DuckDNS

Chrome en Android solo instala la PWA completa si la app se sirve por HTTPS. Caddy obtiene un certificado de Let's Encrypt con el **reto DNS** de DuckDNS, así que no hace falta abrir nada a internet.

1. En duckdns.org, apunta el subdominio a la **IP de WireGuard del VPS** (no a la pública). Escribe la IP en *current ip* y pulsa **update ip** en esa fila.
2. Guarda el token de DuckDNS (arriba en duckdns.org) como secreto `DUCKDNS_TOKEN`.
3. Crea la variable `APP_DOMAIN` con el subdominio completo.
4. Despliega. El primer despliegue compila Caddy con el módulo de DuckDNS y tarda unos minutos más.

Comprobación en el VPS:

```bash
docker compose logs caddy | grep -i "certificate obtained"
```

Si el móvil no resuelve el dominio con la VPN conectada, puede que su DNS bloquee respuestas con IPs privadas (protección contra *DNS rebinding*: algunos routers, NextDNS o el "DNS privado" de Android). Solución: desactivar el DNS privado de Android o poner en la configuración WireGuard del móvil un DNS que no filtre.

## Operación

Desde el VPS, en `/opt/acuario`:

```bash
docker compose ps                     # estado de los contenedores
docker compose logs -f app            # logs de la app
docker compose logs -f caddy          # logs de HTTPS / certificados
docker compose restart app            # reiniciar la app
docker compose exec app python manage.py createsuperuser   # usuario para /admin/
```

Copia de la base de datos (a mano, hasta que se automaticen las copias):

```bash
docker compose exec app python -c "import sqlite3; s=sqlite3.connect('/data/db.sqlite3'); d=sqlite3.connect('/data/backup.sqlite3'); s.backup(d)"
docker compose cp app:/data/backup.sqlite3 ./backup-$(date +%F).sqlite3
```

## Si algo falla

- **"Faltan secretos o variables"**: revisa el paso 2.
- **"Host key verification failed"**: `VPS_SSH_KNOWN_HOSTS` no coincide con `VPS_HOST`; vuelve a ejecutar el script con `PUBLIC_HOST=<el mismo valor que VPS_HOST>`.
- **"cannot assign requested address"** al arrancar: WireGuard no está activo o `WG_BIND_IP` no es la IP de la interfaz (`ip -4 addr show wg0`).
- **"Faltan secretos o variables: DUCKDNS_TOKEN"**: has definido `APP_DOMAIN` sin el token.
- **Caddy no obtiene el certificado**: revisa `docker compose logs caddy`; lo habitual es un token de DuckDNS incorrecto o que el subdominio no pertenezca a esa cuenta.
- **La app no llega a "healthy"**: el workflow muestra los últimos logs de la app en el propio paso.
