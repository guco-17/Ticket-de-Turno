# Ticket de Turno

Ticket de Turno es una aplicación web para registrar y administrar solicitudes de atención relacionadas con trámites educativos. La persona solicitante captura sus datos, selecciona un municipio y el trámite que necesita; el sistema asigna un turno consecutivo para ese municipio y genera un comprobante descargable en PDF con un código QR.

El personal administrador puede consultar y actualizar las solicitudes, revisar indicadores de atención y mantener los catálogos de municipios y estatus. El proyecto está desarrollado en Python con Flask, utiliza MySQL para guardar la información y organiza sus responsabilidades mediante una arquitectura por capas basada en MVC y programación orientada a objetos.

## Objetivo y alcance

El sistema centraliza el registro de solicitudes y facilita el seguimiento de su atención. Sus funciones principales son:

- Registrar solicitudes desde un formulario público.
- Asignar turnos independientes por municipio y evitar números duplicados.
- Consultar y modificar una solicitud usando el CURP y el turno asignado.
- Descargar un comprobante PDF con los datos del trámite y un QR que contiene el CURP.
- Permitir al personal autorizado buscar, registrar, editar, eliminar y cambiar el estatus de las solicitudes.
- Mostrar un tablero con totales, porcentajes y gráficas por estatus y municipio.
- Administrar municipios y estatus desde catálogos.
- Exponer los datos y operaciones principales mediante una API REST JSON.

Los estatus base son **Pendiente** y **Resuelto**. El comprobante confirma que la solicitud quedó registrada; no significa que el trámite ya haya sido resuelto.

## Cómo funciona

### Flujo de una solicitud pública

1. La persona abre **Generar turno** y captura el CURP del alumno, nombre, apellidos, teléfono, correo, municipio, nivel educativo y trámite.
2. El navegador valida los campos y envía los datos en JSON al servidor, junto con un token CSRF.
3. Flask valida nuevamente la información en el servidor: formato del CURP, datos obligatorios, teléfono de diez dígitos, correo y opciones permitidas.
4. El sistema guarda la solicitud con estatus **Pendiente** y le asigna el siguiente turno disponible para el municipio elegido.
5. El servidor genera el PDF en memoria y lo devuelve como descarga. El documento incluye folio, turno, municipio, datos de contacto y del trámite, fecha de registro y un QR con el CURP.

Cada municipio tiene su propio contador persistente. Al mover una solicitud a otro municipio se le asigna un turno nuevo en el destino; si se modifica sin cambiar de municipio, conserva el turno. La combinación de municipio y turno es única en la base de datos. Para consultar o modificar una solicitud pública se necesita el CURP y el número de turno.

### Flujo administrativo

El administrador inicia sesión en **Acceso administradores** y puede:

- Consultar solicitudes por coincidencia parcial de CURP o por palabras del nombre y apellidos. La búsqueda muestra hasta 100 resultados.
- Registrar una solicitud, editar sus datos o eliminarla.
- Cambiar su estatus entre los disponibles.
- Consultar las métricas globales o filtrar el tablero por municipio.
- Agregar, renombrar, activar, desactivar o eliminar municipios, y administrar estatus adicionales.

Los municipios inactivos dejan de aparecer en el formulario público. Los registros de catálogo que tienen solicitudes asociadas no se pueden eliminar; si se trata de un municipio, puede desactivarse en lugar de eliminarse. Los estatus **Pendiente** y **Resuelto** son registros protegidos del sistema.

## Arquitectura y componentes

La aplicación separa la recepción de peticiones, las reglas de negocio, el acceso a datos y la presentación:

- **Modelos — `models/`:** clases ORM para `Municipio`, `Estatus`, `Usuario` y `Solicitud`, además de una clase base común. Representan las entidades, sus relaciones y operaciones de dominio.
- **Controladores — `controllers/`:** reciben las peticiones Flask y coordinan los servicios para devolver páginas HTML, archivos PDF o respuestas JSON. Hay controladores para el sitio público, autenticación, solicitudes administrativas, catálogos y API.
- **Servicios — `services/`:** encapsulan reglas de autenticación, protección CSRF, validación de solicitudes, asignación de turnos, consultas de catálogos, cálculo de estadísticas y generación de comprobantes.
- **Vistas — `templates/`:** páginas Jinja2 para bienvenida, formulario público, acceso administrativo, tablero, solicitudes y catálogos.
- **Recursos del navegador — `static/`:** CSS para la interfaz y JavaScript para el formulario, el CAPTCHA, las confirmaciones administrativas y la actualización de gráficas.
- **Persistencia — `database/`:** script SQL para crear la base y sus tablas iniciales.
- **Pruebas — `tests/`:** pruebas de los flujos públicos, autenticación, administración, catálogos, API, tablero y patrones de diseño.

El recorrido habitual de una petición es: **navegador → controlador → servicio de dominio → modelo/SQLAlchemy → base de datos**. Para el registro público, la respuesta vuelve en forma de comprobante PDF. Para el tablero, el navegador consulta la API y actualiza las métricas y gráficas.

### Patrones de diseño

El código incluye tres patrones que permiten separar y reutilizar responsabilidades:

1. **Singleton:** `DatabaseSingleton` proporciona una instancia compartida de SQLAlchemy para la aplicación.
2. **Factory:** `ApplicationFactory` construye la aplicación Flask y registra sus componentes. `CatalogoFactory` crea descriptores de catálogo de municipios o estatus usando una interfaz común.
3. **Observer:** `SolicitudEventSubject` notifica eventos como creación, edición, cambio de estatus y eliminación. `AuditLogObserver` registra los eventos en memoria y en el logger de Python. El historial en memoria está limitado a los 200 eventos más recientes; no es una bitácora persistente y se pierde al reiniciar el proceso.

## Modelo de datos

La base de datos contiene cuatro tablas principales:

| Tabla | Propósito |
|---|---|
| `municipios` | Catálogo de municipios, estado activo y contador del último turno. |
| `estatus` | Estados asignables a las solicitudes, incluidos los estados base. |
| `usuarios` | Cuentas administrativas activas o inactivas y hashes de contraseña. |
| `solicitudes` | Datos del solicitante, municipio, turno, trámite, estatus y fechas de registro y actualización. |

Una solicitud pertenece a un municipio y a un estatus. La base establece unicidad para el CURP y para la combinación de municipio y turno, y utiliza claves foráneas para las relaciones. SQLAlchemy gestiona las consultas y transacciones; al asignar turnos, el servicio bloquea el registro del municipio durante la operación para coordinar la actualización del contador.

## Interfaz y tecnologías

- **Servidor:** Python 3, Flask y Flask-SQLAlchemy.
- **Base de datos:** MySQL o MariaDB, conectada mediante PyMySQL.
- **Vistas:** Jinja2 y Bootstrap 5.3.3, con estilos propios en `static/css/style.css`.
- **Interactividad:** JavaScript del navegador; el tablero utiliza Chart.js 4.4.7 para gráficas de dona y barras, con una alternativa de dibujo cuando Chart.js no está disponible.
- **Comprobantes:** ReportLab genera el PDF y `qrcode` crea la imagen QR; Pillow se utiliza, entre otras cosas, para generar la imagen del CAPTCHA.
- **Configuración local:** `python-dotenv` carga las variables del archivo `.env`.

Bootstrap y Chart.js se cargan desde CDN en las plantillas, por lo que la interfaz necesita conexión a esos recursos externos si no se sirven localmente.

## API REST

La API devuelve y recibe JSON bajo el prefijo `/api/v1`. Los recursos administrativos requieren una sesión iniciada; las operaciones que modifican datos requieren además el token CSRF en la cabecera `X-CSRF-Token`.

| Método | Ruta | Acceso | Descripción |
|---|---|---|---|
| `GET` | `/api/v1/municipios` | Público | Lista los municipios activos. |
| `GET` | `/api/v1/solicitudes/<curp>/<turno>` | Público | Consulta los datos públicos de una solicitud; se usa para cargarla y modificarla. |
| `GET` | `/api/v1/dashboard/estatus` | Administrador | Devuelve métricas globales o filtradas con `?municipio_id=<id>`. |
| `GET` | `/api/v1/solicitudes` | Administrador | Busca por `criterio` (`nombre` o `curp`) y `q`; admite filtros `municipio_id` y `estatus_id`. |
| `GET` | `/api/v1/solicitudes/<id>` | Administrador | Devuelve el detalle de una solicitud. |
| `PATCH` | `/api/v1/solicitudes/<id>/estatus` | Administrador + CSRF | Actualiza el estatus mediante `estatus_id` o `estatus`. |
| `DELETE` | `/api/v1/solicitudes/<id>` | Administrador + CSRF | Elimina una solicitud. |
| `GET` | `/api/v1/auditoria` | Administrador | Consulta los eventos disponibles en la bitácora en memoria del proceso. |

Los formularios públicos también usan `POST /buscar-solicitud` para la búsqueda con CURP y turno, y `POST /generar-turno` para registrar o actualizar una solicitud y recibir su comprobante PDF.

## Seguridad y consideraciones

- Las contraseñas de los administradores se almacenan como hashes; no se guardan en texto plano.
- El acceso de administración requiere una cuenta activa. El sistema no define roles diferentes: las cuentas de la tabla `usuarios` tienen acceso administrativo.
- El inicio de sesión usa un CAPTCHA de seis caracteres y tokens CSRF. El CAPTCHA se valida una sola vez y se guarda como digest en la sesión, no como texto legible.
- Las rutas privadas requieren sesión; la cookie de sesión se configura como `HttpOnly` y `SameSite=Lax`. La duración por defecto es de 30 minutos y puede cambiarse con `SESSION_MINUTES`.
- Las páginas administrativas se envían con encabezados para evitar su almacenamiento en caché.
- Para una instalación real, configura un `SECRET_KEY` aleatorio y privado, protege las credenciales de la base de datos y no uses el servidor de desarrollo de Flask ni `--debug` en producción. El CAPTCHA local no reemplaza límites de intentos ni otras medidas antiabuso.
- El PDF se genera y se entrega directamente; no se guarda en el servidor. El QR contiene el CURP, por lo que el comprobante debe tratarse como información personal.

## Requisitos

- Python 3.11 o superior.
- MySQL 8.0, MariaDB 10.4 o un servidor compatible.
- Git para clonar el repositorio (opcional).

## Instalación y ejecución en Windows

Los comandos siguientes se ejecutan desde la carpeta raíz del proyecto.

### 1. Crear el entorno e instalar dependencias

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Si PowerShell bloquea la activación del entorno, permite scripts solo para la sesión actual y vuelve a activarlo:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Edita `.env` con los datos de tu instalación. Las variables disponibles son:

| Variable | Descripción | Valor de ejemplo |
|---|---|---|
| `SECRET_KEY` | Clave privada de Flask para sesiones y CAPTCHA. Reemplaza el valor de ejemplo por uno aleatorio. | `replace-with-a-random-secret` |
| `DB_HOST` | Dirección del servidor de base de datos. | `127.0.0.1` |
| `DB_PORT` | Puerto de MySQL o MariaDB. | `3306` |
| `DB_NAME` | Nombre de la base de datos. | `ticket_turno` |
| `DB_USER` | Usuario de base de datos. | `root` |
| `DB_PASSWORD` | Contraseña de base de datos. | (vacía en la plantilla) |
| `SESSION_MINUTES` | Duración de la sesión administrativa en minutos. | `30` |

No publiques el archivo `.env` ni incluyas sus valores en capturas o documentación compartida.

### 2. Crear la base de datos

Inicia MySQL/MariaDB y carga el script incluido. En Windows, desde PowerShell:

```powershell
cmd /c "mysql -u root -p < database\ticket_turno.sql"
```

Si usas XAMPP, puedes ejecutar:

```powershell
cmd /c "C:\xampp\mysql\bin\mysql.exe -u root < database\ticket_turno.sql"
```

El script crea `ticket_turno`, las tablas y los municipios y estatus iniciales. Si cambiaste nombre, usuario, contraseña, host o puerto, actualiza las variables correspondientes en `.env`.

Para una base ya existente de una versión anterior, el comando siguiente es repetible: agrega las columnas de solicitud que falten, verifica los municipios iniciales y ajusta los contadores de turno para que no queden por debajo de los turnos registrados.

```powershell
flask --app app preparar-solicitudes
```

### 3. Crear una cuenta administrativa

Con la base de datos configurada, ejecuta el comando y responde las preguntas interactivas:

```powershell
flask --app app crear-admin
```

El comando solicita usuario, nombre completo y contraseña. La contraseña debe tener al menos 12 caracteres y se guarda como hash.

### 4. Iniciar la aplicación

```powershell
flask --app app run --debug
```

Abre <http://127.0.0.1:5000>. Las rutas principales son:

- `/` y `/solicitud`: formulario público para registrar, buscar y modificar solicitudes.
- `/welcome`: página de bienvenida.
- `/admin/login`: acceso del administrador.
- `/admin`: tablero de control.
- `/admin/solicitudes`: búsqueda y gestión de solicitudes.
- `/admin/catalogos/municipios` y `/admin/catalogos/estatus`: administración de catálogos.

`--debug` se recomienda únicamente para desarrollo local.

## Pruebas

Las pruebas usan una base SQLite en memoria configurada por los propios tests; no requieren conectarse a la base MySQL de la aplicación.

```powershell
python -m unittest discover -s tests -v
```

La suite comprueba, entre otros aspectos, la asignación y modificación de turnos, la creación de PDF y QR, el acceso y cierre de sesión, la protección CSRF, las operaciones de administración y catálogos, los endpoints REST, el cálculo de métricas y los patrones de diseño.

## Estructura del proyecto

```text
.
├── app.py                       # Fábrica y punto de entrada de Flask; comandos CLI
├── admin.py                     # Registro del blueprint de administración
├── api.py                       # Registro del blueprint REST
├── auth.py                      # Fachada de autenticación y protección de rutas
├── catalogos.py                 # Registro del blueprint de catálogos
├── solicitudes.py               # Fachada de validación y asignación de turnos
├── receipts.py                  # Fachada de generación de PDF y QR
├── config.py                    # Configuración de aplicación y conexión a MySQL
├── extensions.py                # Singleton y extensión SQLAlchemy
├── controllers/                 # Controladores MVC y rutas de cada área
├── services/                    # Servicios de autenticación, negocio y estadísticas
├── models/                      # Modelos ORM y entidades del dominio
├── patterns/                    # Implementaciones Singleton, Factory y Observer
├── database/
│   └── ticket_turno.sql         # Esquema y datos iniciales de MySQL
├── templates/                   # Plantillas Jinja2 de la interfaz
├── static/
│   ├── css/style.css            # Estilos propios
│   ├── js/                      # Comportamiento del formulario, panel y administración
│   └── img/logo.jpg             # Logotipo
├── tests/                       # Pruebas automatizadas
├── requirements.txt             # Dependencias de Python
└── .env.example                 # Plantilla de variables de entorno
```
