import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone


class SolicitudObserver(ABC):
    """Interfaz Observer para reaccionar a eventos del ciclo de vida de una solicitud."""

    @abstractmethod
    def actualizar(self, evento: str, datos: dict) -> None:
        pass


class AuditLogObserver(SolicitudObserver):
    """Observador concreto que registra eventos de solicitudes en una bitácora en memoria y logger."""

    def __init__(self):
        self._logger = logging.getLogger("ticket_turno.auditoria")
        self._historial: list[dict] = []

    def actualizar(self, evento: str, datos: dict) -> None:
        entrada = {
            "evento": evento,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **datos,
        }
        self._historial.append(entrada)
        if len(self._historial) > 200:
            self._historial.pop(0)
        self._logger.info("Evento de solicitud [%s]: %s", evento, datos)

    @property
    def historial(self) -> list[dict]:
        return list(self._historial)


class SolicitudEventSubject:
    """Sujeto (Observable) del patrón Observer que administra suscriptores y emite notificaciones."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._observadores = []
        return cls._instance

    def suscribir(self, observador: SolicitudObserver) -> None:
        if observador not in self._observadores:
            self._observadores.append(observador)

    def desuscribir(self, observador: SolicitudObserver) -> None:
        if observador in self._observadores:
            self._observadores.remove(observador)

    def notificar(self, evento: str, datos: dict) -> None:
        for observador in list(self._observadores):
            observador.actualizar(evento, datos)


solicitud_events = SolicitudEventSubject()
auditoria_observer = AuditLogObserver()
solicitud_events.suscribir(auditoria_observer)

