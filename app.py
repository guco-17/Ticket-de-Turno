from io import BytesIO
import re

import click
from flask import Flask, current_app, jsonify, render_template, request, send_file
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from werkzeug.security import generate_password_hash
from reportlab.platypus.doctemplate import LayoutError

from auth import auth, get_csrf_token, verify_csrf_token
from config import Config
from extensions import db
# Importing the models registers their tables with SQLAlchemy metadata.
from models import Estatus, Municipio, Solicitud, Usuario
from receipts import build_ticket_receipt

MUNICIPIOS_INICIALES = (
    "Acuña",
    "Arteaga",
    "Monclova",
    "Parras",
    "Ramos Arizpe",
    "Saltillo",
    "Torreón",
)
NIVELES_EDUCATIVOS = {
    "preescolar",
    "kinder",
    "primaria",
    "secundaria",
    "bachillerato",
    "licenciatura",
    "maestria",
    "doctorado",
}
ASUNTOS = {
    "inscripcion",
    "reinscripcion",
    "cambio_escuela",
    "duplicado_certificado",
    "aclaracion_datos",
}
CURP_PATTERN = re.compile(
    r"^[A-Z][AEIOU][A-Z]{2}\d{2}"
    r"(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])[HM]"
    r"(AS|BC|BS|CC|CL|CM|CS|CH|DF|DG|GT|GR|HG|JC|MC|MN|MS|NT|NL|OC|PL|QT|QR|SP|SL|SR|TC|TS|TL|VZ|YN|ZS|NE)"
    r"[B-DF-HJ-NP-TV-Z]{3}[A-Z0-9]\d$"
)


def _request_payload():
    if not verify_csrf_token(request.headers.get("X-CSRF-Token", "")):
        return None, (
            jsonify(
                {
                    "mensaje": (
                        "La sesión expiró. Recarga la página e inténtalo nuevamente."
                    )
                }
            ),
            400,
        )
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return None, (
            jsonify({"mensaje": "La solicitud no tiene un formato válido."}),
            400,
        )
    return payload, None


def _ticket_identity(payload):
    curp = str(payload.get("curp", "")).strip().upper()
    raw_turn = payload.get("turno")
    if not CURP_PATTERN.fullmatch(curp):
        return None, None, "Captura un CURP válido de 18 caracteres."
    try:
        turno = int(raw_turn)
    except (TypeError, ValueError):
        return None, None, "Escribe el número de turno asignado."
    if turno < 1 or str(raw_turn).strip() != str(turno):
        return None, None, "El número de turno debe ser un entero positivo."
    return curp, turno, None


def _validated_submission(payload):
    fields = {
        "curp": str(payload.get("curp", "")).strip().upper(),
        "nombre": str(payload.get("nombre", "")).strip(),
        "apellido_paterno": str(payload.get("primer_apellido", "")).strip(),
        "apellido_materno": str(payload.get("segundo_apellido", "")).strip(),
        "telefono": re.sub(
            r"[\s()-]",
            "",
            str(payload.get("telefono_contacto", "")).strip(),
        ),
        "correo": str(payload.get("correo", "")).strip(),
        "municipio": str(payload.get("municipio", "")).strip(),
        "nivel_educativo": str(payload.get("nivel_educativo", "")).strip(),
        "asunto": str(payload.get("asunto", "")).strip(),
    }
    if not CURP_PATTERN.fullmatch(fields["curp"]):
        return None, "Captura un CURP válido de 18 caracteres."
    required_fields = (
        "nombre",
        "apellido_paterno",
        "apellido_materno",
        "telefono",
        "correo",
        "municipio",
        "nivel_educativo",
        "asunto",
    )
    if any(not fields[field] for field in required_fields):
        return None, "Completa todos los campos del formulario."
    if any(
        len(fields[field]) > maximum
        for field, maximum in (
            ("nombre", 100),
            ("apellido_paterno", 100),
            ("apellido_materno", 100),
            ("telefono", 15),
            ("correo", 120),
        )
    ):
        return None, "Uno o más datos exceden la longitud permitida."
    if not re.fullmatch(r"\d{10}", fields["telefono"]):
        return None, "El teléfono debe contener 10 dígitos."
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", fields["correo"]):
        return None, "Captura un correo electrónico válido."
    if fields["nivel_educativo"] not in NIVELES_EDUCATIVOS:
        return None, "Selecciona un nivel educativo válido."
    if fields["asunto"] not in ASUNTOS:
        return None, "Selecciona un trámite válido."
    return fields, None


def _allocate_turn(municipio):
    locked_municipio = db.session.execute(
        db.select(Municipio)
        .where(Municipio.id == municipio.id)
        .with_for_update()
    ).scalar_one()
    highest_existing_turn = (
        db.session.query(db.func.max(Solicitud.turno))
        .filter_by(municipio_id=municipio.id)
        .scalar()
        or 0
    )
    locked_municipio.ultimo_turno = max(
        locked_municipio.ultimo_turno,
        highest_existing_turn,
    ) + 1
    return locked_municipio.ultimo_turno


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)
    app.register_blueprint(auth)

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
            raise click.ClickException("El usuario debe tener entre 1 y 50 caracteres.")
        if not name or len(name) > 100:
            raise click.ClickException("El nombre debe tener entre 1 y 100 caracteres.")
        if len(password) < 12:
            raise click.ClickException("La contraseña debe tener al menos 12 caracteres.")
        if Usuario.query.filter_by(usuario=username).first() is not None:
            raise click.ClickException("Ya existe una cuenta con ese usuario.")

        db.session.add(
            Usuario(
                usuario=username,
                nombre=name,
                password_hash=generate_password_hash(password),
                activo=True,
            )
        )
        db.session.commit()
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
            if Municipio.query.filter_by(nombre=municipality_name).first() is None:
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

    @app.context_processor
    def inject_csrf_token():
        return {"csrf_token": get_csrf_token}

    @app.route("/")
    def index():
        municipios = (
            Municipio.query.filter_by(activo=True)
            .order_by(Municipio.nombre)
            .all()
        )
        return render_template("index.html", municipios=municipios)

    @app.route("/welcome")
    def welcome():
        return render_template("welcome.html")

    @app.route("/solicitud")
    def solicitud():
        municipios = (
            Municipio.query.filter_by(activo=True)
            .order_by(Municipio.nombre)
            .all()
        )
        return render_template("index.html", municipios=municipios)

    @app.route("/buscar-solicitud", methods=["POST"])
    def buscar_solicitud():
        payload, error = _request_payload()
        if error:
            return error
        curp, turno, validation_error = _ticket_identity(payload)
        if validation_error:
            return jsonify({"mensaje": validation_error}), 400

        solicitud = Solicitud.query.filter_by(curp=curp, turno=turno).first()
        if solicitud is None:
            return jsonify(
                {"mensaje": "No encontramos una solicitud con ese CURP y número de turno."}
            ), 404
        return jsonify(
            {
                "curp": solicitud.curp,
                "nombre": solicitud.nombre,
                "primer_apellido": solicitud.apellido_paterno,
                "segundo_apellido": solicitud.apellido_materno or "",
                "telefono_contacto": solicitud.telefono or "",
                "correo": solicitud.correo or "",
                "municipio": solicitud.municipio.nombre,
                "nivel_educativo": solicitud.nivel_educativo,
                "asunto": solicitud.asunto,
                "turno": solicitud.turno,
            }
        )

    @app.route("/generar-turno", methods=["POST"])
    def generar_turno():
        payload, error = _request_payload()
        if error:
            return error
        fields, validation_error = _validated_submission(payload)
        if validation_error:
            return jsonify({"mensaje": validation_error}), 400

        raw_turn = payload.get("turno")
        solicitud = None
        if raw_turn not in (None, ""):
            curp, turno, identity_error = _ticket_identity(
                {"curp": fields["curp"], "turno": raw_turn}
            )
            if identity_error:
                return jsonify({"mensaje": identity_error}), 400
            solicitud = (
                Solicitud.query.filter_by(curp=curp, turno=turno)
                .with_for_update()
                .first()
            )
            if solicitud is None:
                return jsonify(
                    {"mensaje": "No encontramos una solicitud con ese CURP y número de turno."}
                ), 404
            is_update = True
        else:
            if Solicitud.query.filter_by(curp=fields["curp"]).first() is not None:
                return jsonify(
                    {
                        "mensaje": (
                            "Ya existe una solicitud para ese CURP. Busca el registro "
                            "con su CURP y número de turno para modificarlo."
                        )
                    }
                ), 409
            is_update = False

        municipio = Municipio.query.filter_by(
            nombre=fields["municipio"],
            activo=True,
        ).first()
        if municipio is None:
            return jsonify({"mensaje": "Selecciona un municipio disponible."}), 400
        estatus = Estatus.query.filter_by(nombre="Pendiente").first()
        if estatus is None:
            current_app.logger.error("No está registrado el estatus inicial Pendiente.")
            return jsonify(
                {"mensaje": "El sistema no está configurado para recibir solicitudes."}
            ), 503

        try:
            if is_update:
                if solicitud.municipio_id != municipio.id:
                    solicitud.turno = _allocate_turn(municipio)
                    solicitud.municipio = municipio
            else:
                solicitud = Solicitud(
                    municipio=municipio,
                    turno=_allocate_turn(municipio),
                    curp=fields["curp"],
                    estatus_id=estatus.id,
                )
                db.session.add(solicitud)

            solicitud.curp = fields["curp"]
            solicitud.nombre = fields["nombre"]
            solicitud.apellido_paterno = fields["apellido_paterno"]
            solicitud.apellido_materno = fields["apellido_materno"]
            solicitud.telefono = fields["telefono"]
            solicitud.correo = fields["correo"]
            solicitud.nivel_educativo = fields["nivel_educativo"]
            solicitud.asunto = fields["asunto"]
            db.session.commit()
            db.session.refresh(solicitud)
        except IntegrityError:
            db.session.rollback()
            return jsonify(
                {
                    "mensaje": (
                        "El registro cambió durante el guardado. "
                        "Recarga e inténtalo nuevamente."
                    )
                }
            ), 409
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("No se pudo guardar la solicitud pública.")
            return jsonify(
                {"mensaje": "No fue posible guardar la solicitud. Inténtalo nuevamente."}
            ), 500

        try:
            pdf = build_ticket_receipt(solicitud)
        except (LayoutError, OSError, TypeError, ValueError):
            current_app.logger.exception(
                "La solicitud %s se guardó, pero no se pudo generar el comprobante.",
                solicitud.id,
            )
            return jsonify(
                {
                    "mensaje": (
                        f"La solicitud se guardó con el turno {solicitud.turno}, "
                        "pero no se pudo generar el comprobante. Contacta al área de atención."
                    ),
                    "turno": solicitud.turno,
                    "municipio": solicitud.municipio.nombre,
                }
            ), 500

        filename = f"comprobante-turno-{solicitud.turno}.pdf"
        response = send_file(
            BytesIO(pdf),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Turno-Asignado"] = str(solicitud.turno)
        response.headers["X-Registro-Actualizado"] = str(is_update).lower()
        return response

    return app


app = create_app()

if __name__ == "__main__":
    app.run()
