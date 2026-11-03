import click
from flask import Flask
from sqlalchemy import inspect

from admin import admin
from api import api
from auth import auth, get_csrf_token
from catalogos import catalogos
from config import Config
from controllers.public_controller import PublicController
from extensions import db
# Importing the models registers their tables with SQLAlchemy metadata.
from models import Estatus, Municipio, Solicitud, Usuario

MUNICIPIOS_INICIALES = (
    "Acuña",
    "Arteaga",
    "Monclova",
    "Parras",
    "Ramos Arizpe",
    "Saltillo",
    "Torreón",
)


class ApplicationFactory:
    """Patrón Factory orientado a objetos para construir y configurar la aplicación Flask."""

    def __init__(self, config_class=Config):
        self.config_class = config_class
        self.public_controller = PublicController()

    def create_app(self) -> Flask:
        app = Flask(__name__)
        app.config.from_object(self.config_class)
        db.init_app(app)

        app.register_blueprint(auth)
        app.register_blueprint(admin)
        app.register_blueprint(catalogos)
        app.register_blueprint(api)
        self.public_controller.register_routes(app)
        self._register_context_processors(app)
        self._register_cli_commands(app)
        return app

    @staticmethod
    def _register_context_processors(app: Flask) -> None:
        @app.context_processor
        def inject_csrf_token():
            return {"csrf_token": get_csrf_token}

    @staticmethod
    def _register_cli_commands(app: Flask) -> None:
        @app.cli.command("crear-admin")
        def create_admin():
            """Create an administrator account with a password hash."""
            username = click.prompt("Usuario").strip()
            name = click.prompt("Nombre completo").strip()
            password = click.prompt(
                "Contraseña (mínimo 12 caracteres)",
                hide_input=True,
                confirmation_prompt=True,
            )

            if not username or len(username) > 50:
                raise click.ClickException(
                    "El usuario debe tener entre 1 y 50 caracteres."
                )
            if not name or len(name) > 100:
                raise click.ClickException(
                    "El nombre debe tener entre 1 y 100 caracteres."
                )
            if len(password) < 12:
                raise click.ClickException(
                    "La contraseña debe tener al menos 12 caracteres."
                )
            if Usuario.query.filter_by(usuario=username).first() is not None:
                raise click.ClickException("Ya existe una cuenta con ese usuario.")

            user = Usuario(
                usuario=username,
                nombre=name,
                activo=True,
            )
            user.establecer_password(password)
            user.save()
            click.echo("Cuenta administrativa creada correctamente.")

        @app.cli.command("preparar-solicitudes")
        def prepare_public_requests():
            """Add public-request fields and seed the supported municipalities."""
            inspector = inspect(db.engine)
            existing_columns = {
                column["name"] for column in inspector.get_columns("solicitudes")
            }
            with db.engine.begin() as connection:
                if "nivel_educativo" not in existing_columns:
                    connection.exec_driver_sql(
                        "ALTER TABLE solicitudes "
                        "ADD COLUMN nivel_educativo VARCHAR(30) NOT NULL DEFAULT ''"
                    )
                if "asunto" not in existing_columns:
                    connection.exec_driver_sql(
                        "ALTER TABLE solicitudes "
                        "ADD COLUMN asunto VARCHAR(50) NOT NULL DEFAULT ''"
                    )

            for municipality_name in MUNICIPIOS_INICIALES:
                if (
                    Municipio.query.filter_by(nombre=municipality_name).first()
                    is None
                ):
                    db.session.add(Municipio(nombre=municipality_name))
            db.session.flush()
            for municipality in Municipio.query.all():
                highest_existing_turn = (
                    db.session.query(db.func.max(Solicitud.turno))
                    .filter_by(municipio_id=municipality.id)
                    .scalar()
                    or 0
                )
                municipality.ultimo_turno = max(
                    municipality.ultimo_turno,
                    highest_existing_turn,
                )
            db.session.commit()
            click.echo(
                "Esquema de solicitudes preparado y municipios iniciales verificados."
            )


def create_app(config_class=Config) -> Flask:
    return ApplicationFactory(config_class).create_app()


app = create_app()

if __name__ == "__main__":
    app.run()
