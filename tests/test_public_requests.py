import unittest

import qrcode

from app import create_app
from extensions import db
from models import Estatus, Municipio, Solicitud
from receipts import build_ticket_receipt, create_curp_qr


class PublicRequestConfig:
    TESTING = True
    SECRET_KEY = "public-request-test-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class PublicRequestTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(PublicRequestConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            db.session.add_all(
                [
                    Estatus(id=1, nombre="Pendiente"),
                    Estatus(id=2, nombre="Resuelto"),
                    Municipio(nombre="Saltillo"),
                    Municipio(nombre="Torreón"),
                ]
            )
            db.session.commit()
            self.saltillo_id = Municipio.query.filter_by(nombre="Saltillo").one().id
            self.torreon_id = Municipio.query.filter_by(nombre="Torreón").one().id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def csrf_headers(self):
        self.client.get("/")
        with self.client.session_transaction() as session:
            token = session["csrf_token"]
        return {"X-CSRF-Token": token}

    @staticmethod
    def submission(curp, municipio="Saltillo", **overrides):
        data = {
            "curp": curp,
            "nombre": "María",
            "primer_apellido": "Gómez",
            "segundo_apellido": "López",
            "telefono_contacto": "8441234567",
            "correo": "maria@example.com",
            "municipio": municipio,
            "nivel_educativo": "primaria",
            "asunto": "inscripcion",
        }
        data.update(overrides)
        return data

    def submit(self, payload):
        return self.client.post(
            "/generar-turno",
            json=payload,
            headers=self.csrf_headers(),
        )

    def test_new_requests_start_at_one_per_municipality_and_return_pdf(self):
        saltillo = self.submit(self.submission("GODE561231HDFRRN09"))
        torreon = self.submit(
            self.submission("JAME900101MDFXXX09", municipio="Torreón")
        )
        next_saltillo_turn = self.submit(
            self.submission("GOME920515MDFRRS01")
        )

        self.assertEqual(saltillo.status_code, 200)
        self.assertEqual(saltillo.mimetype, "application/pdf")
        self.assertTrue(saltillo.data.startswith(b"%PDF-"))
        self.assertEqual(saltillo.headers["X-Turno-Asignado"], "1")
        self.assertIn("attachment;", saltillo.headers["Content-Disposition"])
        qr = create_curp_qr("GODE561231HDFRRN09")
        self.assertEqual(qr.data_list[0].data, b"GODE561231HDFRRN09")
        self.assertEqual(saltillo.data.count(b"/Subtype /Image"), 1)
        self.assertEqual(torreon.status_code, 200)
        self.assertEqual(torreon.headers["X-Turno-Asignado"], "1")
        self.assertEqual(next_saltillo_turn.status_code, 200)
        self.assertEqual(next_saltillo_turn.headers["X-Turno-Asignado"], "2")

        with self.app.app_context():
            saltillo_turns = (
                db.session.query(Solicitud.turno)
                .filter_by(municipio_id=self.saltillo_id)
                .order_by(Solicitud.turno)
                .all()
            )
            torreon_turns = (
                db.session.query(Solicitud.turno)
                .filter_by(municipio_id=self.torreon_id)
                .all()
            )
            self.assertEqual(saltillo_turns, [(1,), (2,)])
            self.assertEqual(torreon_turns, [(1,)])

    def test_receipt_pdf_includes_curp_qr(self):
        self.submit(self.submission("GODE561231HDFRRN09"))
        with self.app.app_context():
            solicitud = Solicitud.query.filter_by(curp="GODE561231HDFRRN09").one()
            receipt = build_ticket_receipt(solicitud)

        self.assertTrue(receipt.startswith(b"%PDF-"))
        self.assertEqual(receipt.count(b"/Subtype /Image"), 1)
        qr = create_curp_qr(solicitud.curp)
        self.assertIsInstance(qr, qrcode.QRCode)
        self.assertEqual(qr.data_list[0].data, solicitud.curp.encode("ascii"))

    def test_update_requires_curp_and_turn_and_preserves_turn_in_same_municipality(self):
        created = self.submit(self.submission("GODE561231HDFRRN09"))
        self.assertEqual(created.status_code, 200)

        found = self.client.post(
            "/buscar-solicitud",
            json={"curp": "GODE561231HDFRRN09", "turno": 1},
            headers=self.csrf_headers(),
        )
        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.json["nombre"], "María")

        wrong_ticket = self.client.post(
            "/buscar-solicitud",
            json={"curp": "GODE561231HDFRRN09", "turno": 2},
            headers=self.csrf_headers(),
        )
        self.assertEqual(wrong_ticket.status_code, 404)

        updated = self.submit(
            self.submission(
                "GODE561231HDFRRN09",
                nombre="Mariana",
                turno="1",
            )
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.headers["X-Turno-Asignado"], "1")
        self.assertEqual(updated.headers["X-Registro-Actualizado"], "true")
        with self.app.app_context():
            request = Solicitud.query.filter_by(curp="GODE561231HDFRRN09").one()
            self.assertEqual(request.nombre, "Mariana")
            self.assertEqual(request.turno, 1)

    def test_changing_municipality_assigns_next_turn_in_destination(self):
        self.submit(self.submission("JAME900101MDFXXX09", municipio="Torreón"))
        self.submit(self.submission("GODE561231HDFRRN09", municipio="Saltillo"))

        moved = self.submit(
            self.submission(
                "GODE561231HDFRRN09",
                municipio="Torreón",
                turno="1",
            )
        )
        self.assertEqual(moved.status_code, 200)
        self.assertEqual(moved.headers["X-Turno-Asignado"], "2")

        with self.app.app_context():
            request = Solicitud.query.filter_by(curp="GODE561231HDFRRN09").one()
            self.assertEqual(request.municipio_id, self.torreon_id)
            self.assertEqual(request.turno, 2)
            saltillo = db.session.get(Municipio, self.saltillo_id)
            torreon = db.session.get(Municipio, self.torreon_id)
            self.assertEqual(saltillo.ultimo_turno, 1)
            self.assertEqual(torreon.ultimo_turno, 2)

    def test_duplicate_curp_without_ticket_is_rejected(self):
        self.submit(self.submission("GODE561231HDFRRN09"))
        duplicate = self.submit(self.submission("GODE561231HDFRRN09"))
        self.assertEqual(duplicate.status_code, 409)
        self.assertIn("Busca el registro", duplicate.json["mensaje"])

    def test_missing_csrf_and_invalid_form_are_rejected(self):
        missing_csrf = self.client.post(
            "/generar-turno",
            json=self.submission("GODE561231HDFRRN09"),
        )
        invalid_data = self.submit(
            self.submission("INVALID-CURP")
        )
        self.assertEqual(missing_csrf.status_code, 400)
        self.assertEqual(invalid_data.status_code, 400)

    def test_preparation_command_is_repeatable(self):
        runner = self.app.test_cli_runner()
        first_run = runner.invoke(args=["preparar-solicitudes"])
        second_run = runner.invoke(args=["preparar-solicitudes"])

        self.assertEqual(first_run.exit_code, 0, first_run.output)
        self.assertEqual(second_run.exit_code, 0, second_run.output)
        with self.app.app_context():
            self.assertEqual(Municipio.query.count(), 7)


if __name__ == "__main__":
    unittest.main()
