#!/usr/bin/env bash
# Prepara un VPS Ubuntu (con Docker y WireGuard ya instalados) para que
# GitHub Actions despliegue acuar.io por SSH.
#
# Uso (una sola vez, como root):
#   sudo bash setup-vps.sh
#
# Variables opcionales:
#   DEPLOY_USER   usuario de despliegue            (por defecto: deploy)
#   DEPLOY_PATH   directorio de la app             (por defecto: /opt/acuario)
#   WG_IFACE      interfaz de WireGuard            (por defecto: la primera que exista, o wg0)
#   PUBLIC_HOST   IP o dominio público del VPS     (por defecto: se detecta)
#
# Al terminar muestra los valores que hay que guardar en GitHub (Settings →
# Secrets and variables → Actions). La clave privada solo se muestra una vez.

set -euo pipefail

DEPLOY_USER="${DEPLOY_USER:-deploy}"
DEPLOY_PATH="${DEPLOY_PATH:-/opt/acuario}"

info() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[aviso]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[error]\033[0m %s\n' "$*" >&2; exit 1; }

[ "$(id -u)" -eq 0 ] || die "Ejecuta el script como root (sudo bash setup-vps.sh)."
command -v docker >/dev/null || die "Docker no está instalado."
docker compose version >/dev/null 2>&1 || die "Falta el plugin 'docker compose'."
getent group docker >/dev/null || die "No existe el grupo 'docker'."
command -v ssh-keygen >/dev/null || die "Falta ssh-keygen (paquete openssh-client)."

# ---------------------------------------------------------------- WireGuard
if [ -z "${WG_IFACE:-}" ]; then
  WG_IFACE="$( (command -v wg >/dev/null && wg show interfaces 2>/dev/null) | awk '{print $1}' || true)"
  WG_IFACE="${WG_IFACE:-wg0}"
fi
WG_IP="$(ip -4 -o addr show dev "$WG_IFACE" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -n1 || true)"
if [ -z "$WG_IP" ]; then
  warn "No encuentro una IPv4 en la interfaz '$WG_IFACE'. Revisa WireGuard y define WG_IFACE si usa otro nombre."
  WG_IP="<IP del VPS dentro de la VPN>"
fi

# ---------------------------------------------------------------- Puertos libres
# app 7733, ntfy 7734 y, con HTTPS, Caddy en 443 (app) y 8443 (ntfy).
PORTS_BUSY=""
if ! command -v ss >/dev/null; then
  warn "No encuentro 'ss' (paquete iproute2): no he podido comprobar si los puertos 7733, 7734, 443 y 8443 están libres."
else
  for port in 7733 7734 443 8443; do
    # Ocupado si algo escucha en ese puerto en todas las IPs o en la de WireGuard.
    if ss -Htln | awk '{print $4}' | grep -Eq "^(0\.0\.0\.0|\*|\[::\]|${WG_IP//./\\.}):${port}$"; then
      PORTS_BUSY="$PORTS_BUSY $port"
    fi
  done
  if [ -n "$PORTS_BUSY" ]; then
    warn "Puertos ya en uso:$PORTS_BUSY. Cámbialos con las variables de GitHub (APP_PORT, NTFY_PORT, HTTPS_PORT, NTFY_HTTPS_PORT). Detalle: sudo ss -tlnp"
  else
    info "Puertos 7733, 7734, 443 y 8443 libres."
  fi
fi

# ---------------------------------------------------------------- Usuario de despliegue
if id "$DEPLOY_USER" >/dev/null 2>&1; then
  info "El usuario '$DEPLOY_USER' ya existe."
else
  info "Creando el usuario '$DEPLOY_USER' (sin contraseña, solo acceso por clave)."
  adduser --disabled-password --gecos "" "$DEPLOY_USER" >/dev/null
fi
usermod -aG docker "$DEPLOY_USER"

info "Preparando $DEPLOY_PATH."
mkdir -p "$DEPLOY_PATH"
chown "$DEPLOY_USER:$DEPLOY_USER" "$DEPLOY_PATH"
chmod 750 "$DEPLOY_PATH"

# ---------------------------------------------------------------- Clave SSH para GitHub Actions
DEPLOY_HOME="$(getent passwd "$DEPLOY_USER" | cut -d: -f6)"
SSH_DIR="$DEPLOY_HOME/.ssh"
AUTH_KEYS="$SSH_DIR/authorized_keys"
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "$SSH_DIR"
touch "$AUTH_KEYS"
chown "$DEPLOY_USER:$DEPLOY_USER" "$AUTH_KEYS"
chmod 600 "$AUTH_KEYS"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
info "Generando una clave SSH exclusiva para GitHub Actions."
ssh-keygen -q -t ed25519 -N "" -C "github-actions@acuario" -f "$TMP_DIR/deploy_key"
# 'restrict' desactiva reenvío de puertos, agente, X11 y pty: solo ejecución de comandos.
sed -i '/github-actions@acuario$/d' "$AUTH_KEYS"
printf 'restrict %s\n' "$(cat "$TMP_DIR/deploy_key.pub")" >> "$AUTH_KEYS"

# ---------------------------------------------------------------- Docker arranca después de WireGuard
# Los contenedores publican sus puertos en la IP de la VPN: si Docker arranca antes
# que WireGuard tras un reinicio, no podría asignar esa IP.
if systemctl list-unit-files "wg-quick@${WG_IFACE}.service" >/dev/null 2>&1 \
   && systemctl is-enabled --quiet "wg-quick@${WG_IFACE}.service" 2>/dev/null; then
  info "Configurando Docker para arrancar después de wg-quick@${WG_IFACE}."
  install -d /etc/systemd/system/docker.service.d
  cat > /etc/systemd/system/docker.service.d/10-after-wireguard.conf <<EOF
[Unit]
After=wg-quick@${WG_IFACE}.service
Wants=wg-quick@${WG_IFACE}.service
EOF
  systemctl daemon-reload
else
  warn "wg-quick@${WG_IFACE} no está habilitado en systemd; no he podido ordenar el arranque de Docker tras WireGuard."
fi

# ---------------------------------------------------------------- Datos para GitHub
SSH_PORT="$(sshd -T 2>/dev/null | awk '/^port /{print $2; exit}')"
SSH_PORT="${SSH_PORT:-22}"
PASSWORD_AUTH="$(sshd -T 2>/dev/null | awk '/^passwordauthentication /{print $2; exit}')"

if [ -z "${PUBLIC_HOST:-}" ]; then
  PUBLIC_HOST="$(curl -4 -fsS --max-time 5 https://api.ipify.org 2>/dev/null || hostname -I | awk '{print $1}')"
fi
if [ "$SSH_PORT" = "22" ]; then HOST_PATTERN="$PUBLIC_HOST"; else HOST_PATTERN="[$PUBLIC_HOST]:$SSH_PORT"; fi
KNOWN_HOSTS="$(for f in /etc/ssh/ssh_host_*_key.pub; do [ -f "$f" ] && awk -v h="$HOST_PATTERN" '{print h, $1, $2}' "$f"; done)"

if command -v openssl >/dev/null; then
  SECRET_KEY="$(openssl rand -base64 64 | tr -dc 'A-Za-z0-9' | head -c 60)"
else
  SECRET_KEY="$(tr -dc 'A-Za-z0-9' </dev/urandom | head -c 60)"
fi

cat <<EOF

======================================================================
 VPS preparado. Guarda estos valores en GitHub:
 Repositorio → Settings → Secrets and variables → Actions
======================================================================

--- Secrets ---------------------------------------------------------

VPS_HOST
$PUBLIC_HOST

VPS_USER
$DEPLOY_USER

VPS_SSH_KNOWN_HOSTS
$KNOWN_HOSTS

DJANGO_SECRET_KEY
$SECRET_KEY

OPENROUTER_API_KEY
(tu clave de https://openrouter.ai/keys; se puede añadir más adelante)

VPS_SSH_KEY  (clave privada: cópiala entera, líneas BEGIN/END incluidas)
$(cat "$TMP_DIR/deploy_key")

--- Variables -------------------------------------------------------

WG_BIND_IP
$WG_IP
EOF

if [ "$SSH_PORT" != "22" ]; then
  printf '\nVPS_SSH_PORT\n%s\n' "$SSH_PORT"
fi
if [ "$DEPLOY_PATH" != "/opt/acuario" ]; then
  printf '\nDEPLOY_PATH\n%s\n' "$DEPLOY_PATH"
fi

cat <<EOF

======================================================================
 La clave privada no se guarda en el VPS: si la pierdes, vuelve a
 ejecutar el script y actualiza VPS_SSH_KEY en GitHub.
======================================================================
EOF

if [ "$PASSWORD_AUTH" = "yes" ]; then
  warn "SSH admite contraseñas. El specs pide acceso solo por clave: pon 'PasswordAuthentication no' en /etc/ssh/sshd_config.d/ y reinicia ssh (comprueba antes que entras con tu clave)."
fi
