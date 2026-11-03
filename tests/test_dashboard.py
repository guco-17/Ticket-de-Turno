import unittest

from werkzeug.security import generate_password_hash

from app import create_app
from extensions import db
from models import Estatus, Municipio, Solicitud, Usuario


class DashboardTestConfig:
    TESTING = True
    SECRET_KEY = "dashboard-test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(DashboardTestConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            saltillo = Municipio(nombre="Saltillo", ultimo_turno=2, activo=True)
            torreon = Municipio(nombre="Torreón", ultimo_turno=1, activo=True)
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
                        activo=True,
                    ),
                ]
            )
            db.session.flush()
            db.session.add_all(
                [
                    Solicitud(
                        municipio=saltillo,
                        turno=1,
                        curp="GODE561231HDFRRN09",
                        nombre="María",
                        apellido_paterno="Gómez",
                        nivel_educativo="primaria",
                        asunto="inscripcion",
                        estatus_id=1,
                    ),
                    Solicitud(
                        municipio=saltillo,
                        turno=2,
                        curp="JAME900101MDFXXX09",
                        nombre="Jaime",
                        apellido_paterno="Martínez",
                        nivel_educativo="secundaria",
                        asunto="reinscripcion",
                        estatus_id=2,
                    ),
                    Solicitud(
                        municipio=torreon,
                        turno=1,
                        curp="GOME920515MDFRRS01",
                        nombre="Sofía",
                        apellido_paterno="Ramírez",
                        nivel_educativo="bachillerato",
                        asunto="duplicado_certificado",
                        estatus_id=1,
                    ),
                ]
            )
            db.session.commit()
            self.admin_id = Usuario.query.one().id
            self.saltillo_id = saltillo.id
            self.torreon_id = torreon.id

        with self.client.session_transaction() as session:
            session["admin_id"] = self.admin_id
            session["admin_username"] = "admin"
            session["csrf_token"] = "csrf-dashboard-test"

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def test_dashboard_renders_charts_and_total_metrics(self):
        response = self.client.get("/admin")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="estatus-chart"', html)
        self.assertIn('id="municipios-chart"', html)
        self.assertIn('id="filtro-municipio"', html)
        self.assertIn("Todos los municipios (Total)", html)
        self.assertIn('id="kpi-total" class="display-6 fw-bold mb-1">3</div>', html)
        self.assertIn('id="kpi-pendientes" class="display-6 fw-bold text-warning-emphasis mb-1">2</div>', html)
        self.assertIn('id="kpi-resueltos" class="display-6 fw-bold text-success mb-1">1</div>', html)

    def test_dashboard_filters_by_specific_municipality(self):
        response = self.client.get(f"/admin?municipio_id={self.torreon_id}")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn('id="etiqueta-filtro-actual">Torreón</strong>', html)
        self.assertIn('id="kpi-total" class="display-6 fw-bold mb-1">1</div>', html)
        self.assertIn('id="kpi-pendientes" class="display-6 fw-bold text-warning-emphasis mb-1">1</div>', html)
        self.assertIn('id="kpi-resueltos" class="display-6 fw-bold text-success mb-1">0</div>', html)

    def test_dashboard_handles_invalid_municipality_filter_gracefully(self):
        response = self.client.get("/admin?municipio_id=9999")
        html = response.get_data(as_text=True)

        self.assertEqual(response.status_code, 200)
        self.assertIn("Todos los municipios (Total)", html)


if __name__ == "__main__":
    unittest.main()

