# Ticket de Turno

Aplicación web en Flask para capturar solicitudes de atención y generar un ticket de turno. El proyecto incluye una base de datos MySQL, modelos SQLAlchemy y un layout responsivo con Bootstrap 5.

El formulario público registra y modifica solicitudes en MySQL, asigna turnos consecutivos por municipio y descarga un comprobante PDF.

## ORM y conexión a la base de datos

La instancia compartida `db` se declara una sola vez en `extensions.py` y se inicializa con la configuración de cada aplicación en `create_app`. Este patrón de extensión compartida evita crear conexiones manuales globales: SQLAlchemy administra el motor, el ciclo de vida de las sesiones y el pool de conexiones. Los modelos se exportan desde `models` y se registran al crear la aplicación. El esquema se administra mediante `database/ticket_turno.sql`.

## Interfaz

Al abrir la aplicación en `/` aparece el formulario de turnos. El enlace **Inicio** abre la página de bienvenida en `/welcome`, mientras que **Generar turno** abre el formulario en `/solicitud`. Las vistas heredan de `templates/base.html`, que proporciona Bootstrap 5.3.3, navegación adaptable y pie de página común. Los estilos propios están en `static/css/style.css`.

## Acceso de administradores

El acceso está en <http://127.0.0.1:5000/admin/login>. Solo las cuentas activas de la tabla `usuarios` pueden iniciar sesión. El esquema actual no tiene roles separados; por ello, registra en esa tabla únicamente cuentas de administradores. Las contraseñas se guardan con hash, las rutas de administración requieren una sesión autenticada y los formularios de acceso y cierre de sesión usan token CSRF. El CAPTCHA genera un código aleatorio en una imagen PNG, lo valida una sola vez por sesión y no almacena el código en claro.

Con el entorno virtual activo, crea una cuenta administrativa de forma interactiva:

```powershell
flask --app app crear-admin
```

El comando solicita usuario, nombre y una contraseña de al menos 12 caracteres; la contraseña no se imprime ni se agrega al repositorio. Ejecuta el comando una vez por cada administrador autorizado. Protege `SECRET_KEY` con un valor aleatorio propio y no uses la clave de desarrollo en producción. Este CAPTCHA local ayuda a limitar envíos automatizados simples, pero no sustituye servicios anti-bot ni límites de intentos para una instalación expuesta a Internet.

## Registro, modificación y comprobantes de turno

Las rutas públicas `/` y `/solicitud` permiten registrar una solicitud. Para modificar un registro, el usuario busca la solicitud con el **CURP y el número de turno asignado**; una coincidencia exacta carga sus datos para editarlos. Si cambia el municipio, el sistema asigna un nuevo turno en ese municipio; si no cambia, conserva el turno original.

Cada municipio tiene un contador independiente y persistente que comienza en 1. La fila del municipio se bloquea durante la asignación y la base impone unicidad sobre `(municipio_id, turno)` para evitar turnos repetidos. El contador avanza al registrar una solicitud y al trasladarla a otro municipio; una modificación en el mismo municipio conserva su turno.

Al registrar o actualizar correctamente, el navegador descarga un comprobante PDF con folio, turno, municipio, datos básicos del solicitante, fecha y un código QR que contiene el CURP del alumno solicitante. El PDF se entrega como respuesta directa y no se almacena en el servidor. Para preparar una base existente, ejecuta una vez (el comando se puede repetir):

```powershell
flask --app app preparar-solicitudes
```

El comando agrega las columnas faltantes, carga los municipios iniciales que no existan y corrige los contadores para que no queden por debajo de turnos ya registrados. Las instalaciones nuevas pueden importar `database/ticket_turno.sql`. El comprobante confirma el registro, pero no la resolución del trámite.

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
├── receipts.py            # Generación del comprobante PDF
├── config.py              # Configuración y conexión MySQL desde variables de entorno
├── extensions.py          # Extensiones Flask compartidas (SQLAlchemy)
├── models/
│   ├── __init__.py        # Exportación de modelos
│   └── models.py          # Modelos de la base de datos
├── database/
│   └── ticket_turno.sql   # Esquema y datos iniciales
├── templates/
│   ├── base.html          # Layout compartido: Bootstrap, navbar y footer
│   ├── welcome.html       # Página de bienvenida (/welcome)
│   └── index.html         # Formulario para generar turnos
│   └── auth/
│       ├── login.html     # Acceso de administradores
│       └── dashboard.html # Página protegida
├── static/
│   ├── css/style.css      # Estilos de la aplicación
│   ├── js/captcha.js      # Actualización del CAPTCHA
│   ├── img/logo.jpg
│   └── js/script.js       # Validación del formulario de turnos
├── auth.py                # Autenticación, CAPTCHA y protección de rutas
├── tests/
│   ├── test_auth.py       # Pruebas de acceso y CAPTCHA
│   └── test_public_requests.py # Pruebas de registro, edición y turnos
├── requirements.txt
└── .env.example           # Plantilla de configuración; no contiene secretos
```

## Publicar en GitHub

El archivo `.gitignore` excluye el entorno virtual, cachés y `.env`. Antes de publicar, revisa que no haya claves, contraseñas ni datos personales en los cambios:

```bash
git status --short
git add .gitignore .env.example README.md app.py auth.py config.py extensions.py requirements.txt database models static templates tests
git diff --cached
git commit -m "Configura entorno inicial del proyecto"
git remote add origin https://github.com/USUARIO/REPOSITORIO.git
git push -u origin main
```

Si ya existe `origin`, no vuelvas a agregarlo; verifica con `git remote -v` y usa `git push -u origin main`. Sustituye la URL de ejemplo por la del repositorio creado en GitHub.
