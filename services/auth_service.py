import hashlib
import hmac
import io
import secrets

from flask import current_app, session
from PIL import Image, ImageDraw, ImageFont

from models import Usuario


class CsrfProtectionService:
    """Servicio orientado a objetos para la generación y verificación de tokens CSRF."""

    SESSION_KEY = "csrf_token"

    def get_token(self) -> str:
        token = session.get(self.SESSION_KEY)
        if token is None:
            token = secrets.token_urlsafe(32)
            session[self.SESSION_KEY] = token
        return token

    def verify_token(self, token: str) -> bool:
        expected_token = session.get(self.SESSION_KEY, "")
        return (
            bool(expected_token)
            and isinstance(token, str)
            and token.isascii()
            and hmac.compare_digest(token, expected_token)
        )


class CaptchaService:
    """Servicio orientado a objetos para generar y validar retos CAPTCHA en imagen."""

    ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    LENGTH = 6
    SESSION_KEY = "admin_captcha_digest"

    def digest(self, answer: str) -> str:
        secret_key = current_app.secret_key
        if secret_key is None:
            raise RuntimeError("SECRET_KEY debe configurarse para habilitar el CAPTCHA.")
        if isinstance(secret_key, str):
            secret_key = secret_key.encode("utf-8")
        return hmac.new(secret_key, answer.encode("utf-8"), hashlib.sha256).hexdigest()

    def generate_image_bytes(self) -> bytes:
        answer = "".join(
            secrets.choice(self.ALPHABET) for _ in range(self.LENGTH)
        )
        session[self.SESSION_KEY] = self.digest(answer)
        image = Image.new("RGB", (200, 72), color="#f2edf5")
        draw = ImageDraw.Draw(image)
        font = ImageFont.load_default(size=32)

        for index, letter in enumerate(answer):
            x = 17 + index * 29
            y = 18 + secrets.randbelow(10) - 5
            draw.text((x, y), letter, font=font, fill="#43204f")

        for _ in range(8):
            draw.line(
                (
                    secrets.randbelow(200),
                    secrets.randbelow(72),
                    secrets.randbelow(200),
                    secrets.randbelow(72),
                ),
                fill="#a58caf",
                width=1,
            )
        for _ in range(80):
            draw.point(
                (secrets.randbelow(200), secrets.randbelow(72)),
                fill="#8d7895",
            )

        image_data = io.BytesIO()
        image.save(image_data, format="PNG")
        return image_data.getvalue()

    def consume_and_verify(self, supplied_captcha: str) -> bool:
        expected_captcha = session.pop(self.SESSION_KEY, None)
        cleaned = (supplied_captcha or "").strip().upper()
        return (
            expected_captcha is not None
            and len(cleaned) == self.LENGTH
            and hmac.compare_digest(self.digest(cleaned), expected_captcha)
        )


class AuthService:
    """Servicio orientado a objetos para autenticación y sesiones de administradores."""

    def __init__(
        self,
        csrf_service: CsrfProtectionService | None = None,
        captcha_service: CaptchaService | None = None,
    ):
        self.csrf = csrf_service or CsrfProtectionService()
        self.captcha = captcha_service or CaptchaService()

    def get_active_admin(self) -> Usuario | None:
        admin_id = session.get("admin_id")
        if admin_id is None:
            return None
        return Usuario.query.filter_by(id=admin_id, activo=True).first()

    def authenticate(self, username: str, password: str) -> Usuario | None:
        cleaned_user = (username or "").strip()
        if (
            not cleaned_user
            or len(cleaned_user) > 50
            or not password
            or len(password) > 256
        ):
            return None
        user = Usuario.query.filter_by(usuario=cleaned_user, activo=True).first()
        if user is None or not user.verificar_password(password):
            return None
        return user

    def start_session(self, user: Usuario) -> None:
        session.clear()
        session.permanent = True
        session["admin_id"] = user.id
        session["admin_username"] = user.usuario
        self.csrf.get_token()

    def close_session(self) -> None:
        session.clear()

