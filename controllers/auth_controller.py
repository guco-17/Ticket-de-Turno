from functools import wraps

from flask import (
    Blueprint,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services.auth_service import (
    AuthService,
    CaptchaService,
    CsrfProtectionService,
)


class AuthController:
    """Controlador MVC orientado a objetos para autenticación, CAPTCHA y sesión administrativa."""

    def __init__(self, auth_service: AuthService | None = None):
        self.csrf_service = CsrfProtectionService()
        self.captcha_service = CaptchaService()
        self.auth_service = auth_service or AuthService(
            csrf_service=self.csrf_service,
            captcha_service=self.captcha_service,
        )

    def admin_required(self, view):
        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if self.auth_service.get_active_admin() is None:
                self.auth_service.close_session()
                return redirect(url_for("auth.login"))
            response = make_response(view(*args, **kwargs))
            response.headers["Cache-Control"] = "no-store, max-age=0"
            response.headers["Pragma"] = "no-cache"
            return response

        return wrapped_view

    def login_form(self):
        if session.get("admin_id") is not None:
            return redirect(url_for("auth.dashboard"))
        self.csrf_service.get_token()
        return render_template("auth/login.html")

    def captcha_image(self):
        image_bytes = self.captcha_service.generate_image_bytes()
        response = make_response(image_bytes)
        response.mimetype = "image/png"
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    def login_submit(self):
        supplied_captcha = request.form.get("captcha", "")
        supplied_csrf = request.form.get("csrf_token", "")

        csrf_valid = self.csrf_service.verify_token(supplied_csrf)
        captcha_valid = self.captcha_service.consume_and_verify(supplied_captcha)

        if not csrf_valid:
            flash("La sesión expiró. Intenta nuevamente.", "danger")
            return redirect(url_for("auth.login"))
        if not captcha_valid:
            flash("El CAPTCHA es incorrecto o venció. Intenta nuevamente.", "danger")
            return redirect(url_for("auth.login"))

        username = request.form.get("usuario", "")
        password = request.form.get("password", "")
        user = self.auth_service.authenticate(username, password)

        if user is None:
            flash("Usuario o contraseña incorrectos.", "danger")
            return redirect(url_for("auth.login"))

        self.auth_service.start_session(user)
        flash("Sesión iniciada correctamente.", "success")
        return redirect(url_for("auth.dashboard"))

    def dashboard(self):
        return render_template("auth/dashboard.html")

    def logout(self):
        supplied_csrf = request.form.get("csrf_token", "")
        if not self.csrf_service.verify_token(supplied_csrf):
            flash("La sesión expiró. Intenta nuevamente.", "danger")
            return redirect(url_for("auth.dashboard"))

        self.auth_service.close_session()
        flash("La sesión se cerró correctamente.", "success")
        return redirect(url_for("auth.login"))

    def create_blueprint(self) -> Blueprint:
        bp = Blueprint("auth", __name__)
        bp.add_url_rule("/admin/login", endpoint="login", view_func=self.login_form, methods=["GET"])
        bp.add_url_rule(
            "/admin/captcha.png",
            endpoint="captcha_image",
            view_func=self.captcha_image,
            methods=["GET"],
        )
        bp.add_url_rule(
            "/admin/login",
            endpoint="login_submit",
            view_func=self.login_submit,
            methods=["POST"],
        )
        bp.add_url_rule(
            "/admin",
            endpoint="dashboard",
            view_func=self.admin_required(self.dashboard),
            methods=["GET"],
        )
        bp.add_url_rule(
            "/admin/logout",
            endpoint="logout",
            view_func=self.admin_required(self.logout),
            methods=["POST"],
        )
        return bp

