# Ticket de Turno

Aplicación web en Flask para capturar solicitudes de atención y generar un ticket de turno. El proyecto está construido bajo una **arquitectura MVC totalmente Orientada a Objetos (POO)**, incluye una base de datos MySQL administrada mediante **ORM (SQLAlchemy)**, **API REST (`/api/v1`)**, **patrones de diseño (`Singleton`, `Factory` y `Observer`)**, un **tablero (Dashboard) con gráficas interactivas** y un layout responsivo con Bootstrap 5.

El formulario público registra y modifica solicitudes en MySQL, asigna turnos consecutivos por municipio y descarga un comprobante PDF con código QR.

## Arquitectura MVC y Programación Orientada a Objetos (POO)

El sistema separa sus responsabilidades en capas orientadas a objetos:

- **Modelos (`models/`)**: [`BaseModel`](models/models.py), [`Municipio`](models/models.py), [`Estatus`](models/models.py), [`Usuario`](models/models.py) y [`Solicitud`](models/models.py) encapsulan el mapeo ORM y los métodos de negocio (`avanzar_turno`, `es_protegido`, `establecer_password`, `verificar_password`, `nombre_completo`, `actualizar_datos`, `to_dict`, `to_public_dict`).
- **Vistas (`templates/` y `static/`)**: Plantillas Jinja2 responsivas con Bootstrap 5.3.3 y controladores Frontend en JavaScript orientado a objetos ([`DashboardController`](static/js/dashboard.js)).
- **Controladores (`controllers/`)**: Clases controladoras que reciben las peticiones HTTP, coordinan los servicios y devuelven vistas HTML o respuestas JSON:
  - [`PublicController`](controllers/public_controller.py): Portal público y generación de comprobantes PDF.
  - [`AuthController`](controllers/auth_controller.py): Login con CAPTCHA, cierre de sesión y vista del Dashboard.
  - [`AdminSolicitudesController`](controllers/admin_controller.py): Consulta, alta, edición, cambio de estatus y eliminación de solicitudes.
  - [`CatalogoController`](controllers/catalogo_controller.py): CRUD de los catálogos del modelo de datos.
  - [`ApiController`](controllers/api_controller.py): Endpoints de la API REST (`/api/v1`).
- **Servicios de Dominio (`services/`)**: Clases con responsabilidad única para la lógica de negocio: [`AuthService`](services/auth_service.py), [`CaptchaService`](services/auth_service.py), [`CsrfProtectionService`](services/auth_service.py), [`SolicitudService`](services/solicitud_service.py), [`SolicitudValidator`](services/solicitud_service.py), [`TurnAllocatorService`](services/solicitud_service.py), [`CatalogoService`](services/catalogo_service.py), [`DashboardService`](services/dashboard_service.py), [`QrCodeBuilder`](services/receipt_service.py) y [`TicketReceiptGenerator`](services/receipt_service.py).

## Patrones de Diseño Implementados (`patterns/`)

El proyecto implementa tres patrones de diseño clásicos orientados a objetos:

1. **Patrón Singleton (`patterns/singleton.py` y `extensions.py`)**:
   - La clase [`DatabaseSingleton`](extensions.py) garantiza mediante `__new__` que exista una única instancia compartida del gestor ORM `SQLAlchemy` (`db`) en todo el ciclo de vida de la aplicación.
2. **Patrón Factory (`patterns/factory.py` y `app.py`)**:
   - [`CatalogoFactory`](patterns/factory.py) instancia polimórficamente los descriptores de catálogo ([`MunicipioCatalogoDescriptor`](patterns/factory.py) y [`EstatusCatalogoDescriptor`](patterns/factory.py), subclases de la clase abstracta [`CatalogoDescriptor`](patterns/factory.py)).
   - [`ApplicationFactory`](app.py) construye y configura la instancia de la aplicación Flask, registrando Blueprints, extensiones y comandos CLI.
3. **Patrón Observer (`patterns/observer.py`)**:
   - [`SolicitudEventSubject`](patterns/observer.py) (Sujeto observable) notifica automáticamente a los observadores suscritos (que implementan la interfaz abstracta [`SolicitudObserver`](patterns/observer.py), como [`AuditLogObserver`](patterns/observer.py)) cada vez que una solicitud se registra, modifica, cambia de estatus entre *“Pendiente”* y *“Resuelto”* o se elimina.

## ORM y conexión a la base de datos

La instancia compartida `db` es provista por [`DatabaseSingleton`](extensions.py) y se inicializa con la configuración de cada aplicación en [`ApplicationFactory.create_app`](app.py). SQLAlchemy administra el motor, el ciclo de vida de las sesiones, las transacciones y el pool de conexiones. Los modelos se exportan desde `models` y el esquema base se encuentra en `database/ticket_turno.sql`.

## Interfaz

Al abrir la aplicación en `/` aparece el formulario de turnos. El enlace **Inicio** abre la página de bienvenida en `/welcome`, mientras que **Generar turno** abre el formulario en `/solicitud`. Las vistas heredan de `templates/base.html`, que proporciona Bootstrap 5.3.3, navegación adaptable y pie de página común. Los estilos propios están en `static/css/style.css`.

## Acceso de administradores

El acceso está en <http://127.0.0.1:5000/admin/login>. Solo las cuentas activas de la tabla `usuarios` pueden iniciar sesión. El esquema actual no tiene roles separados; por ello, registra en esa tabla únicamente cuentas de administradores. Las contraseñas se guardan con hash, las rutas de administración requieren una sesión autenticada y los formularios de acceso y cierre de sesión usan token CSRF. El CAPTCHA genera un código aleatorio en una imagen PNG, lo valida una sola vez por sesión y no almacena el código en claro.

Con el entorno virtual activo, crea una cuenta administrativa de forma interactiva:

```powershell
flask --app app crear-admin
```

El comando solicita usuario, nombre y una contraseña de al menos 12 caracteres; la contraseña no se imprime ni se agrega al repositorio. Ejecuta el comando una vez por cada administrador autorizado. Protege `SECRET_KEY` con un valor aleatorio propio y no uses la clave de desarrollo en producción. Este CAPTCHA local ayuda a limitar envíos automatizados simples, pero no sustituye servicios anti-bot ni límites de intentos para una instalación expuesta a Internet.

## Menú y cierre de sesión

Con una sesión de administrador, la barra de navegación muestra **Panel**, **Solicitudes**, el submenú **Catálogos** (Municipios y Estatus) y un menú con el nombre de la cuenta que contiene **Cerrar sesión**. La opción de la página actual aparece resaltada. Sin sesión solo se muestran las opciones públicas y **Acceso administradores**.

Medidas de seguridad de la parte privada:

- Cerrar sesión se hace con `POST` y token CSRF, y elimina toda la sesión.
- Las páginas privadas se envían con `Cache-Control: no-store`, por lo que tras cerrar sesión el botón **Atrás** del navegador no vuelve a mostrar datos.
- La sesión vence tras `SESSION_MINUTES` minutos de inactividad (30 por omisión, configurable en `.env`); la cookie es `HttpOnly` y `SameSite=Lax`.

## Tablero (Dashboard) con gráficas y filtro por municipio

En `/admin` ([`templates/auth/dashboard.html`](templates/auth/dashboard.html)), el administrador cuenta con un tablero analítico responsivo que muestra el estado de las solicitudes (**“Pendiente”** y **“Resuelto”**):

- **Filtro dinámico**: Permite seleccionar **Todos los municipios (Total de solicitudes)** o filtrar por un **municipio específico**, actualizando las métricas y gráficas en tiempo real mediante peticiones `fetch` a la API REST (`GET /api/v1/dashboard/estatus`).
- **Indicadores (KPIs)**: Total de solicitudes, total en estatus *“Pendiente”*, total en estatus *“Resuelto”* y porcentaje de resolución.
- **Gráficas interactivas (Chart.js)**:
  1. **Gráfica de Dona**: Proporción de solicitudes *“Pendiente”* vs *“Resuelto”* para el filtro seleccionado.
  2. **Gráfica de Barras**: Comparativa de solicitudes *“Pendiente”* y *“Resuelto”* desglosadas por municipio.
- **Tabla resumen por municipio**: Desglose numérico y porcentaje de avance por cada municipio.

## Estrategia de API REST (`/api/v1`)

El módulo [`api.py`](api.py) y [`ApiController`](controllers/api_controller.py) exponen una API RESTful JSON bajo el prefijo `/api/v1`:

| Método | Ruta | Acceso | Descripción |
| :--- | :--- | :--- | :--- |
| `GET` | `/api/v1/municipios` | Público | Lista los municipios activos en formato JSON. |
| `GET` | `/api/v1/solicitudes/<curp>/<turno>` | Público | Consulta una solicitud pública por CURP y número de turno (consumido por el buscador público). |
| `GET` | `/api/v1/dashboard/estatus` | Admin | Devuelve conteos y porcentajes de estatus (*“Pendiente”* y *“Resuelto”*), totales o filtrados con `?municipio_id=<id>`. |
| `GET` | `/api/v1/solicitudes` | Admin | Busca y filtra solicitudes por `criterio` (`curp` o `nombre`), `q`, `municipio_id` y `estatus_id`. |
| `GET` | `/api/v1/solicitudes/<id>` | Admin | Obtiene el detalle completo de una solicitud por su ID. |
| `PATCH` | `/api/v1/solicitudes/<id>/estatus` | Admin + CSRF | Actualiza el estatus de una solicitud (*“Pendiente”* / *“Resuelto”*) y notifica al patrón `Observer`. |
| `DELETE` | `/api/v1/solicitudes/<id>` | Admin + CSRF | Elimina una solicitud y registra el evento en el `Observer`. |
| `GET` | `/api/v1/auditoria` | Admin | Devuelve el historial de eventos capturados en tiempo real por [`AuditLogObserver`](patterns/observer.py). |

## Gestión de solicitudes (administradores)

Con una sesión de administrador, la opción **Solicitudes** (`/admin/solicitudes`) permite consultar registros por **CURP** (coincidencia parcial) o por **nombre** (cada palabra se busca en nombre y apellidos). Desde los resultados se puede:

- **Registrar** una solicitud nueva; el turno se asigna con el mismo contador por municipio que usa el formulario público.
- **Modificar** los datos de una solicitud; si cambia el municipio se asigna un turno nuevo.
- **Eliminar** una solicitud, previa confirmación.
- **Cambiar el estatus** entre “Pendiente” y “Resuelto”.

Todas las acciones requieren sesión activa y token CSRF.

## Catálogos

Los catálogos del modelo de datos se administran desde **Catálogos** en el menú de administración:

- **Municipios** (`/admin/catalogos/municipios`): registrar, renombrar, activar o desactivar y eliminar. Solo los municipios activos aparecen en el formulario público.
- **Estatus** (`/admin/catalogos/estatus`): registrar, renombrar y eliminar estatus adicionales. “Pendiente” y “Resuelto” los usa el sistema y están protegidos.

Un registro con solicitudes asociadas no se puede eliminar; en el caso de un municipio, desactívalo para retirarlo del formulario. Los nombres no se repiten (sin distinguir mayúsculas).

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
- MySQL 8.0 / MariaDB 10.4 o compatible.
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

Si usas XAMPP en `C:\xampp`:

```powershell
cmd /c "C:\xampp\mysql\bin\mysql.exe -u root < database\ticket_turno.sql"
```

### macOS / Linux

```bash
mysql -u root -p < database/ticket_turno.sql
```

Si el usuario o la base de datos tienen otros valores, ajusta el comando y las variables `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT` y `DB_NAME` en `.env`. El script SQL crea la base `ticket_turno`, sus tablas y los estados iniciales.

## Ejecutar la aplicación y pruebas

Con el entorno virtual activo y `.env` configurado:

```bash
flask --app app run --debug
```

Abre <http://127.0.0.1:5000>. La opción `--debug` es solo para desarrollo; no la uses en producción.

Para ejecutar la suite completa de pruebas automatizadas (40 pruebas unitarias y de integración):

```bash
python -m unittest discover -s tests -v
```

Para comprobar la configuración de dependencias:

```bash
python -m pip check
```

## Estructura

```text
.
├── app.py                        # ApplicationFactory y punto de entrada Flask
├── api.py                        # Blueprint de la API REST (/api/v1)
├── admin.py                      # Blueprint de administración de solicitudes
├── auth.py                       # Blueprint de autenticación, CAPTCHA y sesión
├── catalogos.py                  # Blueprint de CRUD de catálogos
├── solicitudes.py                # Fachada de validación y asignación de turnos
├── receipts.py                   # Fachada de generación de comprobantes PDF y QR
├── config.py                     # Configuración y conexión MySQL desde variables de entorno
├── extensions.py                 # DatabaseSingleton y extensión compartida SQLAlchemy
├── models/                       # Capa Modelo (MVC / ORM Orientado a Objetos)
│   ├── __init__.py               # Exportación de modelos
│   └── models.py                 # BaseModel, Municipio, Estatus, Usuario, Solicitud
├── controllers/                  # Capa Controlador (MVC Orientado a Objetos)
│   ├── __init__.py
│   ├── public_controller.py      # PublicController
│   ├── auth_controller.py        # AuthController (Login, CAPTCHA y Dashboard)
│   ├── admin_controller.py       # AdminSolicitudesController
│   ├── catalogo_controller.py    # CatalogoController
│   └── api_controller.py         # ApiController (/api/v1)
├── services/                     # Capa de Servicios de Negocio (POO)
│   ├── __init__.py
│   ├── auth_service.py           # AuthService, CaptchaService, CsrfProtectionService
│   ├── solicitud_service.py      # SolicitudService, SolicitudValidator, TurnAllocatorService
│   ├── catalogo_service.py       # CatalogoService
│   ├── dashboard_service.py      # DashboardService (métricas y agregaciones ORM)
│   └── receipt_service.py        # QrCodeBuilder, TicketReceiptGenerator
├── patterns/                     # Patrones de Diseño GoF
│   ├── __init__.py
│   ├── singleton.py              # Patrón Singleton (DatabaseSingleton)
│   ├── factory.py                # Patrón Factory (CatalogoFactory y descriptores polimórficos)
│   └── observer.py               # Patrón Observer (SolicitudEventSubject y AuditLogObserver)
├── database/
│   └── ticket_turno.sql          # Esquema MySQL y datos iniciales
├── templates/                    # Capa Vista (MVC)
│   ├── base.html                 # Layout compartido: Bootstrap, navbar y footer
│   ├── welcome.html              # Página de bienvenida (/welcome)
│   ├── index.html                # Formulario público para generar y modificar turnos
│   ├── auth/
│   │   ├── login.html            # Acceso de administradores con CAPTCHA
│   │   └── dashboard.html        # Tablero con gráficas de estatus y filtro por municipio
│   └── admin/
│       ├── solicitudes.html      # Consulta y acciones sobre solicitudes
│       ├── solicitud_form.html   # Alta y edición de solicitudes
│       ├── catalogo.html         # Listado y alta de un catálogo
│       └── catalogo_form.html    # Edición de un registro de catálogo
├── static/
│   ├── css/style.css             # Estilos de la aplicación y del Dashboard
│   ├── js/captcha.js             # Actualización del CAPTCHA
│   ├── js/admin.js               # Confirmación de acciones administrativas
│   ├── js/dashboard.js           # DashboardController (Chart.js + consumo de API REST)
│   ├── js/script.js              # Validación y consumo REST del formulario público
│   └── img/logo.jpg
├── tests/
│   ├── test_auth.py              # Pruebas de acceso y CAPTCHA
│   ├── test_public_requests.py   # Pruebas de registro, edición, PDF y QR
│   ├── test_admin_requests.py    # Pruebas de la gestión administrativa de solicitudes
│   ├── test_catalogos.py         # Pruebas del CRUD de catálogos
│   ├── test_patterns_oop.py      # Pruebas de Singleton, Factory, Observer y POO
│   ├── test_api_rest.py          # Pruebas de los endpoints de la API REST (/api/v1)
│   └── test_dashboard.py         # Pruebas del Tablero (Dashboard) y filtros
├── requirements.txt
└── .env.example                  # Plantilla de configuración; no contiene secretos
```

## Publicar en GitHub

El archivo `.gitignore` excluye el entorno virtual, cachés y `.env`. Antes de publicar, revisa que no haya claves, contraseñas ni datos personales en los cambios:

```bash
git status --short
git diff --cached
git push -u origin seba-branch
```
