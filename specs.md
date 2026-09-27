# acuar.io — Especificaciones del proyecto

> Documento vivo. Recoge las indicaciones del proyecto. Las decisiones abiertas están marcadas como **[PENDIENTE]**.

## 1. Objetivo

Aplicación para llevar el control de los parámetros de un acuario marino, consultable desde un móvil Android. Incluye un chat en el que el modelo consulta los datos mediante SQL para responder preguntas sobre tendencias, resúmenes, etc.

## 2. Repositorio

- Repo: https://github.com/cestort/acuar.io.git
- Es un repo existente que se reutiliza: **se borrará todo su contenido actual** y se empezará desde cero.

## 3. Arquitectura general

```
[Android (PWA)] --(WireGuard VPN)--> [VPS]
                                       ├── Contenedor Docker: app Django (Python) + SQLite (volumen)
                                       └── Contenedor Docker: ntfy (alertas)
                                                │
                           app Django --(HTTPS)--> OpenRouter API (DeepSeek V4 Flash)

[GitHub Actions] --(SSH público, solo clave)--> [VPS]
```

## 4. Componentes

### 4.1 Servidor (VPS)
- VPS ya existente y operativo.
- Despliegue con Docker:
  - Un contenedor para la aplicación Django. La base de datos SQLite vive en un volumen persistente.
  - Un contenedor para ntfy (notificaciones).

### 4.2 Backend
- Lenguaje: Python.
- Framework: Django.
- Funciones:
  - Registro y consulta de parámetros del acuario.
  - Servir la PWA y exponer los datos al cliente.
  - Chat con el LLM, que consulta la base de datos mediante SQL.
  - Comprobación de rangos y envío de alertas.

### 4.3 Base de datos
- **SQLite** (sin pgvector, sin embeddings).
- Fichero en un volumen Docker persistente, fuera del contenedor.
- Búsqueda de texto (notas, diario, documentación) con **SQLite FTS5**.

### 4.4 Chat
- Consultas en lenguaje natural sobre tendencias, resúmenes, etc.
- Modelo LLM: DeepSeek V4 Flash, a través de la API de OpenRouter.
- Enfoque: **el modelo genera consultas SQL** (vía *function calling*) sobre la base de datos, en lugar de RAG vectorial.
- El modelo recibe el esquema de las tablas en el prompt de sistema.
- Fuentes consultables:
  - Mediciones de parámetros.
  - Notas de las mediciones.
  - Diario de mantenimiento (cambios de agua, dosificación, altas de corales/peces, etc.).
  - Documentación subida por el usuario (guías, manuales de química marina), indexada con FTS5.
    - Formatos admitidos: **PDF** (se extrae el texto al subirlo) y **Markdown / texto plano**.
- El chat es **solo de consulta**: no registra ni modifica datos. Las mediciones y el diario se introducen por formulario.
- Seguridad de las consultas del modelo:
  - Conexión SQLite **de solo lectura** para el chat.
  - Solo se permiten sentencias `SELECT`.
  - Límite de filas devueltas y tiempo máximo por consulta.

### 4.5 Cliente
- **PWA** servida por Django, instalable en el móvil Android.
- Accesible solo a través de la VPN WireGuard.
- Debe poder leer y recibir los distintos parámetros del acuario.

### 4.6 Origen de los datos
- Fase inicial: **introducción manual** de las mediciones.
- Futuro: integración con un **KH Guardian** para registrar sus mediciones automáticamente.
- El modelo de datos debe registrar la fuente de cada medición (manual / dispositivo) para admitir nuevas integraciones sin rehacerlo.

### 4.7 Parámetros
Parámetros predefinidos desde el inicio:

| Grupo | Parámetros |
|---|---|
| Físicos | Temperatura, salinidad, pH |
| Mayoritarios | KH, Ca, Mg |
| Nutrientes | NO3, PO4 |

- Además, **parámetros configurables**: el usuario puede añadir parámetros propios desde la app (nombre, unidad, rango objetivo).
- Cada parámetro tiene un rango objetivo (mínimo / máximo) editable, que se usa para las alertas.

### 4.8 Alertas
- Alerta cuando una medición queda fuera del rango objetivo de su parámetro.
- Canal: **ntfy autoalojado** en el VPS; el móvil recibe los avisos a través de la VPN con la app ntfy.

## 5. Red y seguridad
- La conexión entre el cliente Android y el VPS se hace mediante VPN WireGuard.
- La app Django y ntfy solo escuchan en la interfaz de la VPN.
- **Sin login en la app**: la VPN es la única barrera de acceso.
- SSH abierto al público **solo con autenticación por clave** (sin contraseña), usado por el despliegue.

## 6. Despliegue (CI/CD)
- Despliegue al VPS mediante GitHub Actions.
- Acceso del runner al VPS por **SSH público con clave**; la clave y el resto de secretos (clave de OpenRouter, etc.) se guardan en GitHub Secrets.
- El despliegue no debe tocar el volumen de SQLite.

## 7. Copias de seguridad
- **De momento no.** A revisar más adelante (el fichero SQLite es fácil de copiar).

## 8. Decisiones pendientes
- Ninguna por ahora.
