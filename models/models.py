from extensions import db

class Municipio(db.Model):
    __tablename__ = "municipios"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False, unique=True)
    ultimo_turno = db.Column(db.Integer, nullable=False, default=0)
    activo = db.Column(db.Boolean, nullable=False, default=True)

class Estatus(db.Model):
    __tablename__ = "estatus"
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(30), nullable=False, unique=True)

class Usuario(db.Model):
    __tablename__ = "usuarios"
    id = db.Column(db.Integer, primary_key=True)
    usuario = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    creado_en = db.Column(db.DateTime, server_default=db.func.now())

class Solicitud(db.Model):
    __tablename__ = "solicitudes"
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
    estatus_id = db.Column(db.Integer, db.ForeignKey("estatus.id"), nullable=False, default=1)
    creado_en = db.Column(db.DateTime, server_default=db.func.now())
    actualizado_en = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())

    municipio = db.relationship("Municipio", backref="solicitudes")
    estatus = db.relationship("Estatus", backref="solicitudes")