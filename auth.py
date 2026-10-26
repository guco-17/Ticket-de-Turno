import hashlib
import hmac
import io
import secrets
from functools import wraps

from flask import (
    Blueprint,
    current_app,
    make_response,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from PIL import Image, ImageDraw, ImageFont
from werkzeug.security import check_password_hash

from models import Usuario


auth = Blueprint("auth", __name__)
_CAPTCHA_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_CAPTCHA_LENGTH = 6


def get_csrf_token():
    token = session.get("csrf_token")
    if token is None:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def verify_csrf_token(token):
    expected_token = session.get("csrf_token", "")
    return (
        bool(expected_token)
        and token.isascii()
        and hmac.compare_digest(token, expected_token)
    )


def _digest_captcha(answer):
    secret_key = current_app.secret_key
    if secret_key is None:
        raise RuntimeError("SECRET_KEY debe configurarse para habilitar el CAPTCHA.")
    if isinstance(secret_key, str):
        secret_key = secret_key.encode("utf-8")
    return hmac.new(secret_key, answer.encode("utf-8"), hashlib.sha256).hexdigest()


def admin_required(view):
    @wraps(view)
    def wrapped_view(*args, **kwargs):
        admin_id = session.get("admin_id")
        if admin_id is None or Usuario.query.filter_by(
            id=admin_id,
            activo=True,
        ).first() is None:
            session.clear()
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped_view


@auth.get("/admin/login")
def login():
    if session.get("admin_id") is not None:
        return redirect(url_for("auth.dashboard"))
    get_csrf_token()
    return render_template("auth/login.html")


@auth.get("/admin/captcha.png")
def captcha_image():
    answer = "".join(
        secrets.choice(_CAPTCHA_ALPHABET) for _ in range(_CAPTCHA_LENGTH)
    )
    session["admin_captcha_digest"] = _digest_captcha(answer)
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
    response = make_response(image_data.getvalue())
    response.mimetype = "image/png"
    response.headers["Cache-Control"] = "no-store, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@auth.post("/admin/login")
def login_submit():
    expected_captcha = session.pop("admin_captcha_digest", None)
    supplied_captcha = request.form.get("captcha", "").strip().upper()
    supplied_csrf = request.form.get("csrf_token", "")

    csrf_valid = verify_csrf_token(supplied_csrf)
    captcha_valid = (
        expected_captcha is not None
        and len(supplied_captcha) == _CAPTCHA_LENGTH
        and hmac.compare_digest(_digest_captcha(supplied_captcha), expected_captcha)
    )
    if not csrf_valid:
        flash("La sesión expiró. Intenta nuevamente.", "danger")
        return redirect(url_for("auth.login"))
    if not captcha_valid:
        flash("El CAPTCHA es incorrecto o venció. Intenta nuevamente.", "danger")
        return redirect(url_for("auth.login"))

    username = request.form.get("usuario", "").strip()
    password = request.form.get("password", "")
    user = None
    if username and len(username) <= 50 and password and len(password) <= 256:
        user = Usuario.query.filter_by(usuario=username, activo=True).first()

    if user is None or not check_password_hash(user.password_hash, password):
        flash("Usuario o contraseña incorrectos.", "danger")
        return redirect(url_for("auth.login"))

    session.clear()
    session["admin_id"] = user.id
    session["admin_username"] = user.usuario
    get_csrf_token()
    flash("Sesión iniciada correctamente.", "success")
    return redirect(url_for("auth.dashboard"))


@auth.get("/admin")
@admin_required
def dashboard():
    return render_template("auth/dashboard.html")


@auth.post("/admin/logout")
@admin_required
def logout():
    supplied_csrf = request.form.get("csrf_token", "")
    if not verify_csrf_token(supplied_csrf):
        flash("La sesión expiró. Intenta nuevamente.", "danger")
        return redirect(url_for("auth.dashboard"))

    session.clear()
    flash("La sesión se cerró correctamente.", "success")
    return redirect(url_for("auth.login"))
