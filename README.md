# acuar.io

Control de parámetros de un acuario marino: registro de tests, diario de mantenimiento y (próximamente) chat con IA sobre los datos. Las especificaciones están en [specs.md](specs.md).

## Desarrollo local

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env          # y ajusta los valores
export $(grep -v '^#' .env | xargs)

python manage.py migrate      # crea la BD y los 8 parámetros predefinidos
python manage.py runserver
```

Abre http://127.0.0.1:8000.

## Tests

```bash
DJANGO_DEBUG=1 python manage.py test
```

## Despliegue

Automático con GitHub Actions en cada push a `main`. Preparación del VPS y secretos necesarios: [DEPLOY.md](DEPLOY.md).

## Estructura

- `config/` — configuración del proyecto Django (todo lo variable se lee de variables de entorno).
- `aquarium/` — app principal: parámetros, mediciones y diario de mantenimiento.
- `docker/`, `Dockerfile`, `docker-compose.yml` — contenedores de la app y de ntfy.
- `scripts/setup-vps.sh` — preparación del VPS (una sola vez).
- `.github/workflows/deploy.yml` — tests y despliegue.
