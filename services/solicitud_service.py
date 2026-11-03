import re

from extensions import db
from models import Estatus, Municipio, Solicitud
from patterns.observer import solicitud_events


class SolicitudValidator:
    """Validador orientado a objetos para los datos y la identidad de una solicitud."""

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

    def validate_submission(self, payload: dict) -> tuple[dict | None, str | None]:
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
        if not self.CURP_PATTERN.fullmatch(fields["curp"]):
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
        if fields["nivel_educativo"] not in self.NIVELES_EDUCATIVOS:
            return None, "Selecciona un nivel educativo válido."
        if fields["asunto"] not in self.ASUNTOS:
            return None, "Selecciona un trámite válido."
        return fields, None

    def validate_ticket_identity(
        self, payload: dict
    ) -> tuple[str | None, int | None, str | None]:
        curp = str(payload.get("curp", "")).strip().upper()
        raw_turn = payload.get("turno")
        if not self.CURP_PATTERN.fullmatch(curp):
            return None, None, "Captura un CURP válido de 18 caracteres."
        try:
            turno = int(raw_turn)
        except (TypeError, ValueError):
            return None, None, "Escribe el número de turno asignado."
        if turno < 1 or str(raw_turn).strip() != str(turno):
            return None, None, "El número de turno debe ser un entero positivo."
        return curp, turno, None


class TurnAllocatorService:
    """Servicio orientado a objetos para asignar turnos consecutivos por municipio con bloqueo de fila."""

    def allocate_turn(self, municipio: Municipio) -> int:
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
        return locked_municipio.avanzar_turno(highest_existing_turn)


class SolicitudService:
    """Servicio de dominio que coordina búsquedas, registro, edición y notificaciones de solicitudes."""

    CRITERIOS_BUSQUEDA = ("curp", "nombre")
    LIMITE_RESULTADOS = 100

    def __init__(
        self,
        validator: SolicitudValidator | None = None,
        turn_allocator: TurnAllocatorService | None = None,
    ):
        self.validator = validator or SolicitudValidator()
        self.turn_allocator = turn_allocator or TurnAllocatorService()

    @staticmethod
    def _like_pattern(term: str) -> str:
        escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    def search(self, criterio: str, termino: str) -> list[Solicitud]:
        query = Solicitud.query
        if termino and criterio == "curp":
            query = query.filter(
                Solicitud.curp.like(self._like_pattern(termino.upper()), escape="\\")
            )
        elif termino:
            for word in termino.split():
                pattern = self._like_pattern(word)
                query = query.filter(
                    db.or_(
                        Solicitud.nombre.ilike(pattern, escape="\\"),
                        Solicitud.apellido_paterno.ilike(pattern, escape="\\"),
                        Solicitud.apellido_materno.ilike(pattern, escape="\\"),
                    )
                )
        return (
            query.order_by(Solicitud.creado_en.desc(), Solicitud.id.desc())
            .limit(self.LIMITE_RESULTADOS)
            .all()
        )

    def find_by_curp_and_turn(
        self, curp: str, turno: int, for_update: bool = False
    ) -> Solicitud | None:
        query = Solicitud.query.filter_by(curp=curp, turno=turno)
        if for_update:
            query = query.with_for_update()
        return query.first()

    def notify_event(self, evento: str, solicitud: Solicitud) -> None:
        solicitud_events.notificar(
            evento,
            {
                "solicitud_id": solicitud.id,
                "curp": solicitud.curp,
                "turno": solicitud.turno,
                "municipio_id": solicitud.municipio_id,
                "estatus": solicitud.estatus.nombre if solicitud.estatus else None,
            },
        )

