import unittest

from extensions import db
from models import Estatus, Municipio, Solicitud, Usuario
from patterns import (
    AuditLogObserver,
    CatalogoFactory,
    DatabaseSingleton,
    EstatusCatalogoDescriptor,
    MunicipioCatalogoDescriptor,
    SolicitudEventSubject,
    auditoria_observer,
)


class PatternsAndOopTests(unittest.TestCase):
    def test_database_singleton_returns_same_instance(self):
        first = DatabaseSingleton()
        second = DatabaseSingleton()
        self.assertIs(first, second)
        self.assertIs(first.db, db)

    def test_catalogo_factory_creates_polymorphic_descriptors(self):
        municipios = CatalogoFactory.crear("municipios")
        estatus = CatalogoFactory.crear("estatus")
        inexistente = CatalogoFactory.crear("inexistente")

        self.assertIsInstance(municipios, MunicipioCatalogoDescriptor)
        self.assertIsInstance(estatus, EstatusCatalogoDescriptor)
        self.assertIsNone(inexistente)
        self.assertTrue(municipios.tiene_activo)
        self.assertFalse(estatus.tiene_activo)
        self.assertEqual(estatus.protegidos, {"Pendiente", "Resuelto"})

    def test_observer_pattern_notifies_subscribed_observers(self):
        subject = SolicitudEventSubject()
        custom_observer = AuditLogObserver()
        subject.suscribir(custom_observer)
        try:
            subject.notificar(
                "estatus_actualizado",
                {"solicitud_id": 10, "estatus": "Resuelto"},
            )
            self.assertEqual(len(custom_observer.historial), 1)
            self.assertEqual(
                custom_observer.historial[0]["evento"], "estatus_actualizado"
            )
            self.assertIn(
                "estatus_actualizado",
                [item["evento"] for item in auditoria_observer.historial],
            )
        finally:
            subject.desuscribir(custom_observer)

    def test_domain_models_encapsulate_business_methods(self):
        municipio = Municipio(id=1, nombre="Saltillo", ultimo_turno=3, activo=True)
        self.assertEqual(municipio.avanzar_turno(maximo_actual=5), 6)
        self.assertEqual(municipio.to_dict()["ultimo_turno"], 6)

        estatus_pendiente = Estatus(id=1, nombre="Pendiente")
        estatus_extra = Estatus(id=3, nombre="En revisión")
        self.assertTrue(estatus_pendiente.es_protegido())
        self.assertFalse(estatus_extra.es_protegido())

        usuario = Usuario(usuario="admin", nombre="Admin")
        usuario.establecer_password("ClaveSegura123!")
        self.assertTrue(usuario.verificar_password("ClaveSegura123!"))
        self.assertFalse(usuario.verificar_password("OtraClave"))

        solicitud = Solicitud(
            id=1,
            municipio=municipio,
            turno=6,
            curp="GODE561231HDFRRN09",
            nombre="María",
            apellido_paterno="Gómez",
            apellido_materno="López",
            estatus=estatus_pendiente,
        )
        self.assertEqual(solicitud.nombre_completo, "María Gómez López")
        self.assertEqual(solicitud.to_dict()["estatus"], "Pendiente")


if __name__ == "__main__":
    unittest.main()

