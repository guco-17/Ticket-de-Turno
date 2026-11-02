import re

from extensions import db
from models import Municipio, Solicitud

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


def validated_submission(payload):
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


def allocate_turn(municipio):
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
