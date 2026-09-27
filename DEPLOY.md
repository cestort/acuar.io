# Despliegue en el VPS

La app se despliega sola con GitHub Actions en cada push a `main`: primero pasan los tests y después se sube el código al VPS por SSH y se levantan los contenedores con `docker compose`.

```
push a main ──► Tests ──► SSH al VPS ──► docker compose up --build ──► espera a /health/
```

En el VPS corren dos contenedores, con los puertos publicados **solo en la IP de WireGuard**:

| Servicio | Puerto | Para qué |
|---|---|---|
| `app` (Django + gunicorn) | `WG_BIND_IP:8000` | La aplicación |
| `ntfy` | `WG_BIND_IP:8080` | Notificaciones de alertas |

Los datos (SQLite y la caché de ntfy) están en volúmenes de Docker, así que un despliegue nunca los borra.

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

**Variables** (pestaña *Variables*):

| Nombre | Obligatoria | Valor |
|---|---|---|
| `WG_BIND_IP` | Sí | IP del VPS dentro de la VPN, p. ej. `10.8.0.1` |
| `VPS_SSH_PORT` | No | Puerto SSH si no es el 22 |
| `DEPLOY_PATH` | No | Directorio de la app si no es `/opt/acuario` |
| `APP_PORT` | No | Puerto de la app (por defecto `8000`) |
| `NTFY_PORT` | No | Puerto de ntfy (por defecto `8080`) |

Mientras `WG_BIND_IP` no exista, el workflow solo ejecuta los tests y se salta el despliegue.

## 3. Desplegar

Cualquier push a `main` despliega. Para lanzar el primer despliegue sin hacer cambios: **Actions → CI/CD → Run workflow**.

Tras el despliegue, desde el móvil con la VPN conectada:

- App: `http://WG_BIND_IP:8000`
- ntfy: instala la app **ntfy** de Android y añade el servidor `http://WG_BIND_IP:8080`.

En el cliente WireGuard del móvil, `AllowedIPs` debe incluir la IP del VPS en la VPN (p. ej. `10.8.0.1/32` o toda la subred).

## Operación

Desde el VPS, en `/opt/acuario`:

```bash
docker compose ps                     # estado de los contenedores
docker compose logs -f app            # logs de la app
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
- **La app no llega a "healthy"**: el workflow muestra los últimos logs de la app en el propio paso.
