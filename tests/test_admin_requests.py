import unittest

from werkzeug.security import generate_password_hash

from app import create_app
from extensions import db
from models import Estatus, Municipio, Solicitud, Usuario


class AdminRequestConfig:
    TESTING = True
    SECRET_KEY = "admin-request-test-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class AdminRequestTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(AdminRequestConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            saltillo = Municipio(nombre="Saltillo", ultimo_turno=2)
            torreon = Municipio(nombre="Torreón")
            db.session.add_all(
                [
                    Estatus(id=1, nombre="Pendiente"),
                    Estatus(id=2, nombre="Resuelto"),
                    saltillo,
                    torreon,
                    Usuario(
                        usuario="admin",
                        nombre="Administrador",
                        password_hash=generate_password_hash("ClaveSegura123!"),
                    ),
                ]
            )
            db.session.flush()
            db.session.add_all(
                [
                    self.request_row(saltillo, 1, "GODE561231HDFRRN09", "María", "Gómez"),
                    self.request_row(saltillo, 2, "JAME900101MDFXXX09", "Jaime", "Martínez"),
                ]
            )
            db.session.commit()
            self.admin_id = Usuario.query.one().id
            self.maria_id = Solicitud.query.filter_by(nombre="María").one().id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    @staticmethod
    def request_row(municipio, turno, curp, nombre, apellido):
        return Solicitud(
            municipio=municipio,
            turno=turno,
            curp=curp,
            nombre=nombre,
            apellido_paterno=apellido,
            apellido_materno="López",
            telefono="8441234567",
            correo="correo@example.com",
            nivel_educativo="primaria",
            asunto="inscripcion",
            estatus_id=1,
        )

    def login(self):
        with self.client.session_transaction() as session:
            session["admin_id"] = self.admin_id
            session["admin_username"] = "admin"
            session["csrf_token"] = "csrf-test-token"

    @staticmethod
    def form(curp="GOME920515MDFRRS01", **overrides):
        data = {
            "csrf_token": "csrf-test-token",
            "curp": curp,
            "nombre": "Sofía",
            "primer_apellido": "Ramírez",
            "segundo_apellido": "Pérez",
            "telefono_contacto": "8447654321",
            "correo": "sofia@example.com",
            "municipio": "Saltillo",
            "nivel_educativo": "secundaria",
            "asunto": "reinscripcion",
            "estatus_id": "1",
        }
        data.update(overrides)
        return data

    def test_admin_pages_require_login(self):
        for path in (
            "/admin/solicitudes",
            "/admin/solicitudes/nueva",
            f"/admin/solicitudes/{self.maria_id}/editar",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/admin/login", response.headers["Location"])

        response = self.client.post(
            f"/admin/solicitudes/{self.maria_id}/eliminar",
            data={"csrf_token": "csrf-test-token"},
        )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Solicitud, self.maria_id))

    def test_search_by_curp_and_by_name(self):
        self.login()
        by_curp = self.client.get("/admin/solicitudes?criterio=curp&q=gode5612")
        by_name = self.client.get("/admin/solicitudes?criterio=nombre&q=jaime martínez")
        no_match = self.client.get("/admin/solicitudes?criterio=nombre&q=Inexistente")

        self.assertIn("GODE561231HDFRRN09", by_curp.get_data(as_text=True))
        self.assertNotIn("JAME900101MDFXXX09", by_curp.get_data(as_text=True))
        self.assertIn("JAME900101MDFXXX09", by_name.get_data(as_text=True))
        self.assertNotIn("GODE561231HDFRRN09", by_name.get_data(as_text=True))
        self.assertIn("No se encontraron solicitudes", no_match.get_data(as_text=True))

    def test_register_assigns_next_turn(self):
        self.login()
        response = self.client.post("/admin/solicitudes/nueva", data=self.form())

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            solicitud = Solicitud.query.filter_by(curp="GOME920515MDFRRS01").one()
            self.assertEqual(solicitud.turno, 3)
            self.assertEqual(solicitud.estatus.nombre, "Pendiente")

    def test_register_rejects_invalid_and_duplicate_data(self):
        self.login()
        invalid = self.client.post(
            "/admin/solicitudes/nueva",
            data=self.form(telefono_contacto="123"),
        )
        duplicate = self.client.post(
            "/admin/solicitudes/nueva",
            data=self.form(curp="GODE561231HDFRRN09"),
        )
        bad_csrf = self.client.post(
            "/admin/solicitudes/nueva",
            data=self.form(csrf_token="otro-token"),
        )

        self.assertIn("10 dígitos", invalid.get_data(as_text=True))
        self.assertIn("Ya existe otra solicitud", duplicate.get_data(as_text=True))
        self.assertIn("La sesión expiró", bad_csrf.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Solicitud.query.count(), 2)

    def test_edit_updates_fields_and_status(self):
        self.login()
        response = self.client.post(
            f"/admin/solicitudes/{self.maria_id}/editar",
            data=self.form(curp="GODE561231HDFRRN09", nombre="María José", estatus_id="2"),
        )

        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            solicitud = db.session.get(Solicitud, self.maria_id)
            self.assertEqual(solicitud.nombre, "María José")
            self.assertEqual(solicitud.turno, 1)
            self.assertEqual(solicitud.estatus.nombre, "Resuelto")

    def test_change_status_between_pending_and_resolved(self):
        self.login()
        for estatus_id, expected in (("2", "Resuelto"), ("1", "Pendiente")):
            with self.subTest(expected=expected):
                response = self.client.post(
                    f"/admin/solicitudes/{self.maria_id}/estatus",
                    data={
                        "csrf_token": "csrf-test-token",
                        "estatus_id": estatus_id,
                        "next": "/admin/solicitudes?q=Mar%C3%ADa",
                    },
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(
                    response.headers["Location"],
                    "/admin/solicitudes?q=Mar%C3%ADa",
                )
                with self.app.app_context():
                    solicitud = db.session.get(Solicitud, self.maria_id)
                    self.assertEqual(solicitud.estatus.nombre, expected)

    def test_delete_requires_csrf_and_ignores_external_redirects(self):
        self.login()
        rejected = self.client.post(
            f"/admin/solicitudes/{self.maria_id}/eliminar",
            data={"csrf_token": "otro-token"},
        )
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Solicitud, self.maria_id))

        deleted = self.client.post(
            f"/admin/solicitudes/{self.maria_id}/eliminar",
            data={"csrf_token": "csrf-test-token", "next": "//evil.example"},
        )

        self.assertEqual(rejected.status_code, 302)
        self.assertEqual(deleted.status_code, 302)
        self.assertEqual(deleted.headers["Location"], "/admin/solicitudes")
        with self.app.app_context():
            self.assertIsNone(db.session.get(Solicitud, self.maria_id))


if __name__ == "__main__":
    unittest.main()
