import unittest

from werkzeug.security import generate_password_hash

from app import create_app
from extensions import db
from models import Estatus, Municipio, Solicitud, Usuario


class ApiRestTestConfig:
    TESTING = True
    SECRET_KEY = "api-rest-test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class ApiRestTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(ApiRestTestConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            saltillo = Municipio(nombre="Saltillo", ultimo_turno=2, activo=True)
            torreon = Municipio(nombre="Torreón", ultimo_turno=1, activo=True)
            inactivo = Municipio(nombre="Parras", ultimo_turno=0, activo=False)
            db.session.add_all(
                [
                    Estatus(id=1, nombre="Pendiente"),
                    Estatus(id=2, nombre="Resuelto"),
                    saltillo,
                    torreon,
                    inactivo,
                    Usuario(
                        usuario="admin",
                        nombre="Administrador",
                        password_hash=generate_password_hash("ClaveSegura123!"),
                        activo=True,
                    ),
                ]
            )
            db.session.flush()
            sol1 = Solicitud(
                municipio=saltillo,
                turno=1,
                curp="GODE561231HDFRRN09",
                nombre="María",
                apellido_paterno="Gómez",
                apellido_materno="López",
                telefono="8441234567",
                correo="maria@example.com",
                nivel_educativo="primaria",
                asunto="inscripcion",
                estatus_id=1,
            )
            sol2 = Solicitud(
                municipio=saltillo,
                turno=2,
                curp="JAME900101MDFXXX09",
                nombre="Jaime",
                apellido_paterno="Martínez",
                apellido_materno="Pérez",
                telefono="8449876543",
                correo="jaime@example.com",
                nivel_educativo="secundaria",
                asunto="reinscripcion",
                estatus_id=2,
            )
            sol3 = Solicitud(
                municipio=torreon,
                turno=1,
                curp="GOME920515MDFRRS01",
                nombre="Sofía",
                apellido_paterno="Ramírez",
                apellido_materno="Díaz",
                telefono="8711112233",
                correo="sofia@example.com",
                nivel_educativo="bachillerato",
                asunto="duplicado_certificado",
                estatus_id=1,
            )
            db.session.add_all([sol1, sol2, sol3])
            db.session.commit()
            self.admin_id = Usuario.query.one().id
            self.saltillo_id = saltillo.id
            self.torreon_id = torreon.id
            self.sol1_id = sol1.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def login_admin(self):
        with self.client.session_transaction() as session:
            session["admin_id"] = self.admin_id
            session["admin_username"] = "admin"
            session["csrf_token"] = "csrf-api-test"
        return {"X-CSRF-Token": "csrf-api-test"}

    def test_public_endpoints_municipios_and_solicitud_lookup(self):
        municipios = self.client.get("/api/v1/municipios")
        self.assertEqual(municipios.status_code, 200)
        nombres = [m["nombre"] for m in municipios.json["municipios"]]
        self.assertEqual(nombres, ["Saltillo", "Torreón"])

        found = self.client.get("/api/v1/solicitudes/gode561231hdfrrn09/1")
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json["curp"], "GODE561231HDFRRN09")
        self.assertEqual(found.json["turno"], 1)

        not_found = self.client.get("/api/v1/solicitudes/GODE561231HDFRRN09/99")
        self.assertEqual(not_found.status_code, 404)

        invalid_curp = self.client.get("/api/v1/solicitudes/INVALID/1")
        self.assertEqual(invalid_curp.status_code, 400)

    def test_private_api_endpoints_require_authentication(self):
        for path in (
            "/api/v1/dashboard/estatus",
            "/api/v1/solicitudes",
            f"/api/v1/solicitudes/{self.sol1_id}",
            "/api/v1/auditoria",
        ):
            with self.subTest(path=path):
                res = self.client.get(path)
                self.assertEqual(res.status_code, 401)

    def test_dashboard_estatus_endpoint_total_and_filtered_by_municipality(self):
        self.login_admin()

        total_stats = self.client.get("/api/v1/dashboard/estatus")
        self.assertEqual(total_stats.status_code, 200)
        self.assertEqual(total_stats.json["resumen"]["total"], 3)
        self.assertEqual(total_stats.json["resumen"]["pendientes"], 2)
        self.assertEqual(total_stats.json["resumen"]["resueltos"], 1)

        saltillo_stats = self.client.get(
            f"/api/v1/dashboard/estatus?municipio_id={self.saltillo_id}"
        )
        self.assertEqual(saltillo_stats.status_code, 200)
        self.assertEqual(
            saltillo_stats.json["filtro"]["municipio_nombre"], "Saltillo"
        )
        self.assertEqual(saltillo_stats.json["resumen"]["total"], 2)
        self.assertEqual(saltillo_stats.json["resumen"]["pendientes"], 1)
        self.assertEqual(saltillo_stats.json["resumen"]["resueltos"], 1)

        missing_mun = self.client.get("/api/v1/dashboard/estatus?municipio_id=999")
        self.assertEqual(missing_mun.status_code, 404)

        invalid_mun = self.client.get("/api/v1/dashboard/estatus?municipio_id=abc")
        self.assertEqual(invalid_mun.status_code, 400)

    def test_patch_status_and_delete_solicitud_via_rest_api(self):
        headers = self.login_admin()

        missing_csrf = self.client.patch(
            f"/api/v1/solicitudes/{self.sol1_id}/estatus",
            json={"estatus": "Resuelto"},
        )
        self.assertEqual(missing_csrf.status_code, 400)

        patched = self.client.patch(
            f"/api/v1/solicitudes/{self.sol1_id}/estatus",
            json={"estatus": "Resuelto"},
            headers=headers,
        )
        self.assertEqual(patched.status_code, 200)
        self.assertEqual(patched.json["solicitud"]["estatus"], "Resuelto")

        auditoria = self.client.get("/api/v1/auditoria")
        self.assertEqual(auditoria.status_code, 200)
        self.assertGreaterEqual(auditoria.json["total"], 1)

        deleted = self.client.delete(
            f"/api/v1/solicitudes/{self.sol1_id}",
            headers=headers,
        )
        self.assertEqual(deleted.status_code, 200)
        self.assertEqual(
            self.client.get(f"/api/v1/solicitudes/{self.sol1_id}").status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()

