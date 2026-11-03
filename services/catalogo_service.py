from extensions import db
from models import Solicitud
from patterns.factory import CatalogoDescriptor, CatalogoFactory


class CatalogoService:
    """Servicio orientado a objetos para administrar los catálogos del sistema."""

    def get_descriptor(self, clave: str) -> CatalogoDescriptor | None:
        return CatalogoFactory.crear(clave)

    def usage_map(self, descriptor: CatalogoDescriptor) -> dict[int, int]:
        return dict(
            db.session.query(descriptor.referencia, db.func.count(Solicitud.id))
            .group_by(descriptor.referencia)
            .all()
        )

    def usage_count(self, descriptor: CatalogoDescriptor, registro_id: int) -> int:
        return (
            db.session.query(db.func.count(Solicitud.id))
            .filter(descriptor.referencia == registro_id)
            .scalar()
        )

    def validate_name(
        self,
        descriptor: CatalogoDescriptor,
        raw_name: str,
        registro=None,
    ) -> tuple[str | None, str | None]:
        nombre = " ".join((raw_name or "").split())
        if not nombre:
            return None, "Escribe un nombre."
        if len(nombre) > descriptor.longitud:
            return (
                None,
                f"El nombre admite como máximo {descriptor.longitud} caracteres.",
            )
        modelo = descriptor.modelo
        duplicate = modelo.query.filter(
            db.func.lower(modelo.nombre) == nombre.lower(),
            modelo.id != (registro.id if registro else 0),
        ).first()
        if duplicate is not None:
            return None, f"Ya existe un {descriptor.singular} con ese nombre."
        return nombre, None

    def list_records(self, descriptor: CatalogoDescriptor) -> list:
        modelo = descriptor.modelo
        return modelo.query.order_by(modelo.nombre).all()

