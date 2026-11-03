from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db


class BaseModel(db.Model):
    """Clase base abstracta de dominio para los modelos ORM."""

    __abstract__ = True

    def save(self):
        db.session.add(self)
        db.session.commit()
        return self

    def delete(self):
        db.session.delete(self)
        db.session.commit()


class Municipio(BaseModel):
    __tablename__ = "municipios"

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    ultimo_turno = db.Column(db.Integer, nullable=False, default=0)
    activo = db.Column(db.Boolean, nullable=False, default=True)

    def avanzar_turno(self, maximo_actual: int = 0) -> int:
        """Incrementa y devuelve el siguiente número de turno del municipio."""
        self.ultimo_turno = max(self.ultimo_turno or 0, maximo_actual) + 1
        return self.ultimo_turno

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "ultimo_turno": self.ultimo_turno,
            "activo": bool(self.activo),
        }


class Estatus(BaseModel):
    __tablename__ = "estatus"

    ESTATUS_SISTEMA = frozenset({"Pendiente", "Resuelto"})

    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(30), nullable=False, unique=True)

    def es_protegido(self) -> bool:
        """Indica si el estatus pertenece a los estados base del sistema."""
        return self.nombre in self.ESTATUS_SISTEMA

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "protegido": self.es_protegido(),
        }


class Usuario(BaseModel):
    __tablename__ = "usuarios"

    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, server_default=db.func.now())

    def establecer_password(self, password_plana: str) -> None:
        self.password_hash = generate_password_hash(password_plana)

    def verificar_password(self, password_plana: str) -> bool:
        return check_password_hash(self.password_hash, password_plana)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "usuario": self.usuario,
            "nombre": self.nombre,
            "activo": bool(self.activo),
        }


class Solicitud(BaseModel):
    __tablename__ = "solicitudes"
    __table_args__ = (
        db.UniqueConstraint("municipio_id", "turno", name="uq_turno_municipio"),
    )

    id = db.Column(db.Integer, primary_key=True)
    municipio_id = db.Column(db.Integer, db.ForeignKey("municipios.id"), nullable=False)
    turno = db.Column(db.Integer, nullable=False)
    curp = db.Column(db.String(18), nullable=False, unique=True)
    nombre = db.Column(db.String(100), nullable=False)
    apellido_paterno = db.Column(db.String(100), nullable=False)
    apellido_materno = db.Column(db.String(100))
    fecha_nacimiento = db.Column(db.Date)
    telefono = db.Column(db.String(15))
    correo = db.Column(db.String(120))
    nivel_educativo = db.Column(db.String(30), nullable=False, default="")
    asunto = db.Column(db.String(50), nullable=False, default="")
    estatus_id = db.Column(db.Integer, db.ForeignKey("estatus.id"), nullable=False, default=1)
    creado_en = db.Column(db.DateTime, server_default=db.func.now())
    actualizado_en = db.Column(
        db.DateTime,
        server_default=db.func.now(),
        onupdate=db.func.now(),
    )

    municipio = db.relationship("Municipio", backref="solicitudes")
    estatus = db.relationship("Estatus", backref="solicitudes")

    @property
    def nombre_completo(self) -> str:
        return " ".join(
            part
            for part in (
                self.nombre,
                self.apellido_paterno,
                self.apellido_materno,
            )
            if part
        )

    def actualizar_datos(self, campos: dict) -> None:
        """Actualiza los campos del solicitante a partir de un diccionario validado."""
        self.curp = campos["curp"]
        self.nombre = campos["nombre"]
        self.apellido_paterno = campos["apellido_paterno"]
        self.apellido_materno = campos["apellido_materno"]
        self.telefono = campos["telefono"]
        self.correo = campos["correo"]
        self.nivel_educativo = campos["nivel_educativo"]
        self.asunto = campos["asunto"]

    def to_public_dict(self) -> dict:
        return {
            "curp": self.curp,
            "nombre": self.nombre,
            "primer_apellido": self.apellido_paterno,
            "segundo_apellido": self.apellido_materno or "",
            "telefono_contacto": self.telefono or "",
            "correo": self.correo or "",
            "municipio": self.municipio.nombre if self.municipio else "",
            "nivel_educativo": self.nivel_educativo,
            "asunto": self.asunto,
            "turno": self.turno,
        }

    def to_dict(self) -> dict:
        data = self.to_public_dict()
        data.update(
            {
                "id": self.id,
                "municipio_id": self.municipio_id,
                "estatus_id": self.estatus_id,
                "estatus": self.estatus.nombre if self.estatus else "",
                "nombre_completo": self.nombre_completo,
                "creado_en": (
                    self.creado_en.isoformat() if self.creado_en else None
                ),
            }
        )
        return data
