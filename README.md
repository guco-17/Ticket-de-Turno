# Ticket de Turno

Aplicación web en Flask para capturar solicitudes de atención y generar un ticket de turno. El proyecto incluye una base de datos MySQL y modelos SQLAlchemy.

> Estado actual: el formulario valida los datos y responde al envío, pero la ruta `/generar-turno` todavía no guarda solicitudes en MySQL ni asigna un número de turno.

## Requisitos

- Python 3.11 o superior.
- MySQL 8.0 o compatible.
- Git (opcional, para clonar y publicar el proyecto).

## Preparar el entorno

Desde la carpeta raíz del proyecto, crea y activa un entorno virtual.

### Windows (PowerShell)

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Si PowerShell bloquea la activación, permite scripts para la sesión actual con `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` y vuelve a activar el entorno.

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
cp .env.example .env
```

Edita `.env` y configura las credenciales de tu MySQL local. Define también un `SECRET_KEY` aleatorio; no compartas ni subas ese archivo al repositorio.

## Preparar la base de datos

Con MySQL iniciado y un usuario con permisos para crear bases de datos, importa el esquema incluido desde la carpeta raíz del proyecto.

### Windows (PowerShell)

```powershell
$env:Path += ";$env:ProgramFiles\MySQL\MySQL Server 8.0\bin"
cmd /c "mysql -u root -p < database\ticket_turno.sql"
```

Si instalaste MySQL en otra ubicación, agrega a `PATH` la carpeta que contiene `mysql.exe`.

### macOS / Linux

```bash
mysql -u root -p < database/ticket_turno.sql
```

Si el usuario o la base de datos tienen otros valores, ajusta el comando y las variables `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` y `DB_NAME` en `.env`. El script SQL crea la base `ticket_turno`, sus tablas y los estados iniciales.

## Ejecutar la aplicación

Con el entorno virtual activo y `.env` configurado:

```bash
flask --app app run --debug
```

Abre <http://127.0.0.1:5000>. La opción `--debug` es solo para desarrollo; no la uses en producción.

Para comprobar la configuración de dependencias:

```bash
python -m pip check
```

## Estructura

```text
.
├── app.py                 # Aplicación Flask y rutas HTTP
├── config.py              # Configuración y conexión MySQL desde variables de entorno
├── extensions.py          # Extensiones Flask compartidas (SQLAlchemy)
├── models/
│   └── models.py          # Modelos de la base de datos
├── database/
│   └── ticket_turno.sql   # Esquema y datos iniciales
├── templates/
│   └── index.html         # Formulario principal
├── static/
│   ├── css/style.css
│   ├── img/logo.jpg
│   └── js/script.js
├── requirements.txt
└── .env.example           # Plantilla de configuración; no contiene secretos
```

## Publicar en GitHub

El archivo `.gitignore` excluye el entorno virtual, cachés y `.env`. Antes de publicar, revisa que no haya claves, contraseñas ni datos personales en los cambios:

```bash
git status --short
git add .gitignore .env.example README.md app.py config.py extensions.py requirements.txt database models static templates
git diff --cached
git commit -m "Configura entorno inicial del proyecto"
git remote add origin https://github.com/USUARIO/REPOSITORIO.git
git push -u origin main
```

Si ya existe `origin`, no vuelvas a agregarlo; verifica con `git remote -v` y usa `git push -u origin main`. Sustituye la URL de ejemplo por la del repositorio creado en GitHub.
