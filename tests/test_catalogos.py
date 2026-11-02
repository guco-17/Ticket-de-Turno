import unittest

from werkzeug.security import generate_password_hash

from app import create_app
from extensions import db
from models import Estatus, Municipio, Solicitud, Usuario


class CatalogConfig:
    TESTING = True
    SECRET_KEY = "catalog-test-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class CatalogTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(CatalogConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            saltillo = Municipio(nombre="Saltillo", ultimo_turno=1)
            db.session.add_all(
                [
                    Estatus(id=1, nombre="Pendiente"),
                    Estatus(id=2, nombre="Resuelto"),
                    Estatus(id=3, nombre="Cancelado"),
                    saltillo,
                    Municipio(nombre="Parras"),
                    Usuario(
                        usuario="admin",
                        nombre="Administrador",
                        password_hash=generate_password_hash("ClaveSegura123!"),
                    ),
                ]
            )
            db.session.flush()
            db.session.add(
                Solicitud(
                    municipio=saltillo,
                    turno=1,
                    curp="GODE561231HDFRRN09",
                    nombre="María",
                    apellido_paterno="Gómez",
                    nivel_educativo="primaria",
                    asunto="inscripcion",
                    estatus_id=1,
                )
            )
            db.session.commit()
            self.admin_id = Usuario.query.one().id
            self.saltillo_id = saltillo.id
            self.parras_id = Municipio.query.filter_by(nombre="Parras").one().id

        with self.client.session_transaction() as session:
            session["admin_id"] = self.admin_id
            session["admin_username"] = "admin"
            session["csrf_token"] = "csrf-test-token"

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def post(self, path, **data):
        data.setdefault("csrf_token", "csrf-test-token")
        return self.client.post(path, data=data)

    def test_catalog_pages_list_records_and_require_login(self):
        municipios = self.client.get("/admin/catalogos/municipios")
        estatus = self.client.get("/admin/catalogos/estatus")
        unknown = self.client.get("/admin/catalogos/usuarios")

        self.assertIn("Parras", municipios.get_data(as_text=True))
        self.assertIn("Cancelado", estatus.get_data(as_text=True))
        self.assertEqual(unknown.status_code, 404)

        with self.client.session_transaction() as session:
            session.clear()
        self.assertEqual(self.client.get("/admin/catalogos/municipios").status_code, 302)

    def test_create_municipality_and_reject_duplicates(self):
        created = self.post("/admin/catalogos/municipios", nombre="  Ramos   Arizpe ", activo="1")
        duplicate = self.post("/admin/catalogos/municipios", nombre="saltillo")
        bad_csrf = self.post(
            "/admin/catalogos/municipios",
            nombre="Monclova",
            csrf_token="otro-token",
        )

        self.assertEqual(created.status_code, 302)
        self.assertEqual(duplicate.status_code, 302)
        self.assertEqual(bad_csrf.status_code, 302)
        with self.app.app_context():
            municipio = Municipio.query.filter_by(nombre="Ramos Arizpe").one()
            self.assertTrue(municipio.activo)
            self.assertEqual(Municipio.query.count(), 3)

    def test_deactivated_municipality_is_hidden_from_public_form(self):
        response = self.post(
            f"/admin/catalogos/municipios/{self.parras_id}/editar",
            nombre="Parras de la Fuente",
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            municipio = db.session.get(Municipio, self.parras_id)
            self.assertEqual(municipio.nombre, "Parras de la Fuente")
            self.assertFalse(municipio.activo)
        self.assertNotIn(
            'value="Parras de la Fuente"',
            self.client.get("/").get_data(as_text=True),
        )

    def test_delete_only_unused_records(self):
        in_use = self.post(f"/admin/catalogos/municipios/{self.saltillo_id}/eliminar")
        unused = self.post(f"/admin/catalogos/municipios/{self.parras_id}/eliminar")

        self.assertEqual(in_use.status_code, 302)
        self.assertEqual(unused.status_code, 302)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Municipio, self.saltillo_id))
            self.assertIsNone(db.session.get(Municipio, self.parras_id))

    def test_status_catalog_crud_protects_system_statuses(self):
        self.post("/admin/catalogos/estatus", nombre="En revisión")
        self.post("/admin/catalogos/estatus/3/editar", nombre="Cancelada")
        renamed_protected = self.post("/admin/catalogos/estatus/1/editar", nombre="Abierto")
        self.post("/admin/catalogos/estatus/2/eliminar")
        self.post("/admin/catalogos/estatus/3/eliminar")

        self.assertIn("no se puede renombrar", renamed_protected.get_data(as_text=True))
        with self.app.app_context():
            nombres = {estatus.nombre for estatus in Estatus.query.all()}
        self.assertEqual(nombres, {"Pendiente", "Resuelto", "En revisión"})


if __name__ == "__main__":
    unittest.main()
