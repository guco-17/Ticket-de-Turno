from abc import ABC, abstractmethod

from models import Estatus, Municipio, Solicitud


class CatalogoDescriptor(ABC):
    """Clase base abstracta para descriptores de catálogo (Herencia y Polimorfismo)."""

    @property
    @abstractmethod
    def clave(self) -> str:
        pass

    @property
    @abstractmethod
    def modelo(self):
        pass

    @property
    @abstractmethod
    def referencia(self):
        pass

    @property
    @abstractmethod
    def titulo(self) -> str:
        pass

    @property
    @abstractmethod
    def singular(self) -> str:
        pass

    @property
    @abstractmethod
    def longitud(self) -> int:
        pass

    @property
    @abstractmethod
    def tiene_activo(self) -> bool:
        pass

    @property
    def protegidos(self) -> set[str]:
        return set()

    def es_protegido(self, registro) -> bool:
        return False

    def crear_instancia(self, nombre: str, activo: bool = True):
        instancia = self.modelo(nombre=nombre)
        if self.tiene_activo:
            instancia.activo = activo
        return instancia

    def to_dict(self) -> dict:
        return {
            "clave": self.clave,
            "modelo": self.modelo,
            "referencia": self.referencia,
            "titulo": self.titulo,
            "singular": self.singular,
            "longitud": self.longitud,
            "tiene_activo": self.tiene_activo,
        }

    def __getitem__(self, item: str):
        return getattr(self, item)


class MunicipioCatalogoDescriptor(CatalogoDescriptor):
    """Descriptor concreto para el catálogo de Municipios."""

    clave = "municipios"
    modelo = Municipio
    titulo = "Municipios"
    singular = "municipio"
    longitud = 100
    tiene_activo = True

    @property
    def referencia(self):
        return Solicitud.municipio_id


class EstatusCatalogoDescriptor(CatalogoDescriptor):
    """Descriptor concreto para el catálogo de Estatus."""

    clave = "estatus"
    modelo = Estatus
    titulo = "Estatus"
    singular = "estatus"
    longitud = 30
    tiene_activo = False

    @property
    def referencia(self):
        return Solicitud.estatus_id

    @property
    def protegidos(self) -> set[str]:
        return set(Estatus.ESTATUS_SISTEMA)

    def es_protegido(self, registro) -> bool:
        return bool(registro and registro.nombre in Estatus.ESTATUS_SISTEMA)


class CatalogoFactory:
    """Patrón Factory para instanciar descriptores de catálogos según su clave."""

    _REGISTRO: dict[str, type[CatalogoDescriptor]] = {
        MunicipioCatalogoDescriptor.clave: MunicipioCatalogoDescriptor,
        EstatusCatalogoDescriptor.clave: EstatusCatalogoDescriptor,
    }

    @classmethod
    def crear(cls, clave: str) -> CatalogoDescriptor | None:
        descriptor_cls = cls._REGISTRO.get(clave)
        if descriptor_cls is None:
            return None
        return descriptor_cls()

    @classmethod
    def todos(cls) -> dict[str, CatalogoDescriptor]:
        return {clave: descriptor_cls() for clave, descriptor_cls in cls._REGISTRO.items()}
