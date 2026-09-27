# acuar.io — Especificaciones del proyecto

> Documento vivo. Recoge las indicaciones del proyecto. Las decisiones abiertas están marcadas como **[PENDIENTE]**.

## 1. Objetivo

Aplicación para llevar el control de los parámetros de un acuario marino, consultable desde un móvil Android. Incluye un chat que responde preguntas sobre tendencias, resúmenes, etc., consultando los datos por SQL y buscando en notas y documentación mediante RAG.

## 2. Repositorio

- Repo: https://github.com/cestort/acuar.io.git
- Repo reutilizado: su contenido anterior se eliminó y el proyecto empezó desde cero (el código antiguo sigue en el historial, commit `df0a9db`).

## 3. Arquitectura general

```
[Android (PWA)] --(WireGuard VPN)--> https://acuario-esteve-macon.duckdns.org  (DNS → IP de WireGuard del VPS)
                                       │
                                     [VPS] (Docker, proyecto "acuario")
                                       ├── Caddy: HTTPS en 443 (app) y 8443 (ntfy), certificado Let's Encrypt por DNS (DuckDNS)
                                       ├── app: Django + gunicorn, puerto 7733, SQLite en volumen
                                       └── ntfy: alertas, puerto 7734
                                                │
                           app Django --(HTTPS)--> OpenRouter API
                                                    ├── Chat: DeepSeek V4 Flash
                                                    └── Embeddings: bge-m3

[GitHub Actions] --(SSH público, solo clave)--> [VPS]

[KH Guardian] (red de casa, Ethernet) --> recolector --> API de la app   (futuro, ver 4.7)
```

## 4. Componentes

### 4.1 Servidor (VPS)
- VPS ya existente y operativo: Ubuntu, con Docker y WireGuard instalados.
- En el VPS hay otros proyectos que usan DuckDNS y WireGuard, y un **nginx solo HTTP** (puerto 80) como proxy inverso. acuar.io **no toca ese nginx**: usa sus propios puertos y su propio Caddy.
- Despliegue con Docker Compose (proyecto `acuario`):
  - **app**: aplicación Django. La base de datos SQLite vive en un volumen persistente.
  - **ntfy**: notificaciones.
  - **caddy**: HTTPS. Servicio opcional (perfil `https`), se activa al definir el dominio.

### 4.2 Backend
- Lenguaje: Python.
- Framework: Django.
- Funciones:
  - Registro y consulta de parámetros del acuario.
  - Servir la PWA y exponer los datos al cliente.
  - Chat con el LLM, que consulta la base de datos mediante SQL.
  - Comprobación de rangos y envío de alertas.
  - (Futuro) API para recibir mediciones de dispositivos.

### 4.3 Base de datos
- **SQLite** (sin Postgres ni pgvector).
- Fichero en un volumen Docker persistente, fuera del contenedor.
- Búsqueda de texto (notas, diario, documentación):
  - Por palabras clave con **SQLite FTS5**.
  - Por significado con vectores guardados en SQLite mediante la extensión **sqlite-vec**.

### 4.4 Embeddings
- Servicio: **OpenRouter**, modelo **bge-m3** (multilingüe), con la misma clave de API que el chat.
- Sin modelo local: no consume RAM ni CPU del VPS.
- Uso:
  - Al guardar una nota, entrada del diario o documento, se trocea el texto y se calcula el embedding de cada fragmento.
  - Al preguntar en el chat, se calcula el embedding de la pregunta para buscar los fragmentos más parecidos.
- El indexado se hace en segundo plano y es reintentable: si OpenRouter falla, el dato se guarda igual y el embedding queda pendiente.
- Se guarda qué modelo generó cada vector, para poder reindexar si se cambia de modelo.
- Nota de privacidad: el texto de notas, diario y documentos se envía a OpenRouter (igual que las consultas del chat).

### 4.5 Chat
- Consultas en lenguaje natural sobre tendencias, resúmenes, etc.
- Modelo LLM: DeepSeek V4 Flash, a través de la API de OpenRouter.
- Enfoque híbrido mediante *function calling*:
  - **Datos numéricos** (mediciones, tendencias, medias): el modelo genera consultas SQL.
  - **Texto** (notas, diario, documentación): herramienta de búsqueda que combina FTS5 y similitud de embeddings (RAG).
- El modelo recibe el esquema de las tablas en el prompt de sistema.
- Fuentes consultables:
  - Mediciones de parámetros.
  - Notas de las mediciones.
  - Diario de mantenimiento (cambios de agua, dosificación, altas de corales/peces, etc.).
  - Documentación subida por el usuario (guías, manuales de química marina), indexada con FTS5 y embeddings.
    - Formatos admitidos: **PDF** (se extrae el texto al subirlo) y **Markdown / texto plano**.
- El chat es **solo de consulta**: no registra ni modifica datos. Las mediciones y el diario se introducen por formulario.
- Seguridad de las consultas del modelo:
  - Conexión SQLite **de solo lectura** para el chat.
  - Solo se permiten sentencias `SELECT`.
  - Límite de filas devueltas y tiempo máximo por consulta.

### 4.6 Cliente
- **PWA** servida por Django, instalable en el móvil Android.
- URL: **https://acuario-esteve-macon.duckdns.org** (HTTPS, necesario para instalar la PWA completa en Chrome/Android).
- Accesible solo a través de la VPN WireGuard: el dominio apunta a la IP del VPS dentro de la VPN.
- Debe poder leer y recibir los distintos parámetros del acuario.

### 4.7 Origen de los datos
- Fase inicial: **introducción manual** de las mediciones.
- Futuro: integración con un **KH Guardian** para registrar sus mediciones automáticamente.
- El modelo de datos registra la fuente de cada medición (manual / dispositivo) para admitir nuevas integraciones sin rehacerlo.

#### KH Guardian (investigación, sin decidir)
- Equipo de **Dr. Bridge** (distribuido por D-D / CoralVue). Mide **KH** por titración cada 30–240 min y el **pH** de la muestra. Con el módulo opcional **AIM-S** añade temperatura, salinidad, pH y ORP.
- Conexión solo por **Ethernet**, con interfaz web local en `http://IP:8090` (contraseña por defecto "Admin"). **No tiene API oficial**.
- Forma de extraer datos (probada por la comunidad): iniciar sesión en la web local y leer:
  - `GET /Default`: última medida (KH, pH, fecha).
  - `GET /SD_Dump`: histórico completo guardado en la tarjeta SD.
- Referencias: `github.com/cbleehk/khgtools` (Node.js, lectura local y deduplicado por fecha) y el script AppDaemon de marine-assistant.com.
- Riesgos:
  - Se basa en leer HTML: una actualización de firmware puede romperlo, así que el recolector debe avisar si no puede interpretar una medida.
  - Las fechas del equipo no llevan año: hay que deducirlo y vigilar el reloj del equipo.
  - Según usuarios, el pH que da está pensado para la titración (sonda calibrada en rango bajo); para vigilar el pH del acuario es mejor otra sonda.
- Diseño propuesto:
  - Un **recolector** pequeño (script Python) que lea el KH Guardian cada 15–30 min.
  - Lo envía a un **endpoint de la app** autenticado con token.
  - Se guarda con la **fecha de la medida del equipo** (no la de importación) y una **restricción única** (parámetro, origen, fecha) para no duplicar.
  - En la primera ejecución importa el histórico desde `/SD_Dump`.

#### Recolector en casa
- El KH Guardian no lleva módulo AIM-S: solo da KH y el pH de la muestra.
- Un único **recolector en casa** (p. ej. una Raspberry Pi o un equipo siempre encendido) leerá los dispositivos de la red local y enviará las medidas a la app del VPS a través de WireGuard.
- Así se podrán sumar otras sondas en el futuro sin exponer nada de casa a internet.

#### Otras sondas (investigación, sin decidir)
- **Monitores WiFi "7/8 en 1" tipo Tuya** (pH, ORP, EC/TDS, salinidad, densidad, temperatura):
  - Comprobar antes de comprar que su rango de salinidad/EC cubre el agua de mar: muchos están pensados para piscinas o hidroponía.
  - Formas de leerlos en local: con la clave local de Tuya (tuya-local / LocalTuya), o cambiando el firmware del módulo WiFi por OpenBeken (probado en el modelo PH-W218, chip CB3S) para publicar por MQTT sin nube.
- **Montaje casero con ESP32 + ESPHome**: sonda de pH (DFRobot o Atlas Scientific), temperatura y, opcionalmente, conductividad para la salinidad.

### 4.8 Parámetros
Parámetros predefinidos desde el inicio:

| Grupo | Parámetros |
|---|---|
| Físicos | Temperatura, salinidad (densidad, SG), pH |
| Mayoritarios | KH, Ca, Mg |
| Nutrientes | NO3, PO4 |

- Además, **parámetros configurables**: el usuario puede añadir parámetros propios desde la app (nombre, unidad, rango objetivo).
- Cada parámetro tiene un rango objetivo (mínimo / máximo) editable, que se usa para las alertas.

### 4.9 Alertas
- Alerta cuando una medición queda fuera del rango objetivo de su parámetro.
- Canal: **ntfy autoalojado** en el VPS; el móvil recibe los avisos a través de la VPN con la app ntfy.
- URL de ntfy: `https://acuario-esteve-macon.duckdns.org:8443` (o `http://IP-WireGuard:7734` sin HTTPS).

## 5. Red y seguridad
- La conexión entre el cliente Android y el VPS se hace mediante VPN WireGuard.
- Todos los puertos se publican **solo en la IP de WireGuard** del VPS.
- Puertos propios para no chocar con otros proyectos del VPS (todos configurables):

| Servicio | Puerto |
|---|---|
| app (HTTP directo) | 7733 |
| ntfy (HTTP directo) | 7734 |
| Caddy → app (HTTPS) | 443 |
| Caddy → ntfy (HTTPS) | 8443 |

- La IP de publicación es configurable (`BIND_IP`); por defecto la de WireGuard. Docker se salta UFW, así que publicar en `0.0.0.0` abriría los puertos a internet.
- **HTTPS**:
  - Dominio: `acuario-esteve-macon.duckdns.org`, con registro A apuntando a la **IP de WireGuard** del VPS, no a la pública. Desde internet el dominio no lleva a ningún sitio.
  - Certificado de Let's Encrypt obtenido por Caddy con el **reto DNS-01** a través de la API de DuckDNS: no necesita abrir puertos a internet.
  - El token de DuckDNS se guarda en GitHub Secrets (`DUCKDNS_TOKEN`); controla todos los subdominios de la cuenta, así que se trata como una contraseña.
  - Django confía en la cabecera `X-Forwarded-Proto` de Caddy (`DJANGO_BEHIND_HTTPS_PROXY`).
  - Si algún DNS del móvil bloquea respuestas con IPs privadas (protección contra *DNS rebinding*), se usará el DNS del VPS en la configuración WireGuard del móvil.
- **Sin login en la app**: la VPN es la única barrera de acceso.
- SSH abierto al público **solo con autenticación por clave** (sin contraseña), usado por el despliegue.

## 6. Despliegue (CI/CD)
- Despliegue al VPS mediante GitHub Actions (`.github/workflows/deploy.yml`), en cada push a `main`.
- Flujo: tests → subida del código por SSH → `docker compose up -d --build` en el VPS → espera a que `/health/` responda.
- Acceso del runner al VPS por **SSH público con clave**, con un usuario `deploy` dedicado (miembro del grupo `docker`) y una clave exclusiva limitada con `restrict`.
- La clave y el resto de secretos (clave de OpenRouter, `DJANGO_SECRET_KEY`, `DUCKDNS_TOKEN`, etc.) se guardan en GitHub Secrets; el workflow genera el `.env` del VPS en cada despliegue.
- Las imágenes (app y Caddy con el módulo de DuckDNS) se construyen en el propio VPS, sin registro de imágenes. La primera compilación de Caddy tarda unos minutos.
- El despliegue no toca los volúmenes (SQLite, caché de ntfy, certificados de Caddy).
- HTTPS se activa solo al definir la variable `APP_DOMAIN` en GitHub; sin ella se despliega solo por HTTP.
- Docker arranca después de WireGuard (drop-in de systemd), porque los puertos se publican en la IP de la VPN.
- Preparación del VPS con `scripts/setup-vps.sh` (también comprueba que los puertos 7733, 7734, 443 y 8443 estén libres) y guía completa en `DEPLOY.md`.

## 7. Copias de seguridad
- **De momento no.** A revisar más adelante (el fichero SQLite es fácil de copiar).

## 8. Decisiones pendientes
- **[PENDIENTE]** IP del VPS dentro de WireGuard: se usará en la variable `WG_BIND_IP` y en el registro de DuckDNS, que ahora apunta a la IP pública (82.223.152.7) y hay que cambiar.
- **[PENDIENTE]** Ejecutar `scripts/setup-vps.sh` en el VPS y guardar en GitHub los secretos y variables, incluido `DUCKDNS_TOKEN`.
- **[PENDIENTE]** KH Guardian:
  - Sin módulo AIM-S: solo da KH y el pH de la muestra.
  - El recolector correrá **en un equipo de casa** (misma red que el KH Guardian) y enviará los datos a la app del VPS. Falta decidir en qué equipo y cómo llega al VPS (por la VPN WireGuard).
  - Si su pH se registra como parámetro aparte del pH manual.
