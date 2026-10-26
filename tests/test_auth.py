import unittest

from werkzeug.security import check_password_hash, generate_password_hash

from app import create_app
from auth import _digest_captcha
from extensions import db
from models import Usuario


class TestConfig:
    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_TRACK_MODIFICATIONS = False


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            db.session.add(
                Usuario(
                    usuario="admin",
                    nombre="Administrador",
                    password_hash=generate_password_hash("ClaveSegura123!"),
                    activo=True,
                )
            )
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()

    def set_challenge(self, answer="ABC234"):
        with self.app.app_context():
            digest = _digest_captcha(answer)
        with self.client.session_transaction() as session:
            session["csrf_token"] = "csrf-test-token"
            session["admin_captcha_digest"] = digest

    def test_login_page_and_captcha_image(self):
        page = self.client.get("/admin/login")
        captcha = self.client.get("/admin/captcha.png")

        self.assertEqual(page.status_code, 200)
        self.assertIn(b'name="usuario"', page.data)
        self.assertIn(b'name="captcha"', page.data)
        self.assertEqual(captcha.mimetype, "image/png")
        self.assertTrue(captcha.data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertIn("no-store", captcha.headers["Cache-Control"])

    def test_valid_login_protects_and_allows_admin_routes(self):
        self.set_challenge()
        response = self.client.post(
            "/admin/login",
            data={
                "csrf_token": "csrf-test-token",
                "usuario": "admin",
                "password": "ClaveSegura123!",
                "captcha": "ABC234",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/admin")
        self.assertEqual(self.client.get("/admin").status_code, 200)

        with self.client.session_transaction() as session:
            logout_csrf = session["csrf_token"]
        logout = self.client.post(
            "/admin/logout",
            data={"csrf_token": logout_csrf},
        )
        self.assertEqual(logout.status_code, 302)
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def test_deactivated_admin_session_is_revoked(self):
        self.set_challenge()
        response = self.client.post(
            "/admin/login",
            data={
                "csrf_token": "csrf-test-token",
                "usuario": "admin",
                "password": "ClaveSegura123!",
                "captcha": "ABC234",
            },
        )
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            user = Usuario.query.filter_by(usuario="admin").one()
            user.activo = False
            db.session.commit()

        self.assertEqual(self.client.get("/admin").status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn("admin_id", session)

    def test_invalid_captcha_is_rejected_and_consumed(self):
        self.set_challenge()
        response = self.client.post(
            "/admin/login",
            data={
                "csrf_token": "csrf-test-token",
                "usuario": "admin",
                "password": "ClaveSegura123!",
                "captcha": "WRONG1",
            },
        )

        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as session:
            self.assertNotIn("admin_captcha_digest", session)
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def test_invalid_credentials_and_inactive_account_are_rejected(self):
        for username, password in (
            ("admin", "incorrect-password"),
            ("missing", "ClaveSegura123!"),
        ):
            with self.subTest(username=username):
                self.set_challenge()
                response = self.client.post(
                    "/admin/login",
                    data={
                        "csrf_token": "csrf-test-token",
                        "usuario": username,
                        "password": password,
                        "captcha": "ABC234",
                    },
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(self.client.get("/admin").status_code, 302)

        with self.app.app_context():
            user = Usuario.query.filter_by(usuario="admin").one()
            user.activo = False
            db.session.commit()

        self.set_challenge()
        response = self.client.post(
            "/admin/login",
            data={
                "csrf_token": "csrf-test-token",
                "usuario": "admin",
                "password": "ClaveSegura123!",
                "captcha": "ABC234",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.client.get("/admin").status_code, 302)

    def test_non_ascii_csrf_token_is_rejected_without_server_error(self):
        self.set_challenge()
        response = self.client.post(
            "/admin/login",
            data={
                "csrf_token": "á",
                "usuario": "admin",
                "password": "ClaveSegura123!",
                "captcha": "ABC234",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_create_admin_cli_hashes_password(self):
        result = self.app.test_cli_runner().invoke(
            args=["crear-admin"],
            input="newadmin\nNueva Administradora\nClaveNuevaSegura123!\n"
            "ClaveNuevaSegura123!\n",
        )

        self.assertEqual(result.exit_code, 0, result.output)
        with self.app.app_context():
            user = Usuario.query.filter_by(usuario="newadmin").one()
            self.assertNotEqual(user.password_hash, "ClaveNuevaSegura123!")
            self.assertTrue(
                check_password_hash(user.password_hash, "ClaveNuevaSegura123!")
            )


if __name__ == "__main__":
    unittest.main()
