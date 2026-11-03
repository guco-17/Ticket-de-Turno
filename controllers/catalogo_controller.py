from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from extensions import db
from services.auth_service import CsrfProtectionService
from services.catalogo_service import CatalogoService


class CatalogoController:
    """Controlador MVC orientado a objetos para el CRUD de catálogos (Municipios y Estatus)."""

    def __init__(
        self,
        catalogo_service: CatalogoService | None = None,
        csrf_service: CsrfProtectionService | None = None,
    ):
        self.service = catalogo_service or CatalogoService()
        self.csrf = csrf_service or CsrfProtectionService()

    def _descriptor_or_404(self, clave: str):
        descriptor = self.service.get_descriptor(clave)
        if descriptor is None:
            abort(404)
        return descriptor

    def listar(self, clave: str):
        descriptor = self._descriptor_or_404(clave)
        return render_template(
            "admin/catalogo.html",
            clave=clave,
            catalogo=descriptor,
            registros=self.service.list_records(descriptor),
            uso=self.service.usage_map(descriptor),
            protegidos=descriptor.protegidos,
        )

    def crear(self, clave: str):
        descriptor = self._descriptor_or_404(clave)
        if not self.csrf.verify_token(request.form.get("csrf_token", "")):
            flash("La sesión expiró. Intenta nuevamente.", "danger")
            return redirect(url_for("catalogos.listar", clave=clave))

        nombre, error = self.service.validate_name(
            descriptor,
            request.form.get("nombre", ""),
        )
        if error:
            flash(error, "danger")
            return redirect(url_for("catalogos.listar", clave=clave))

        registro = descriptor.crear_instancia(
            nombre=nombre,
            activo=request.form.get("activo") == "1",
        )
        db.session.add(registro)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash(f"Ya existe un {descriptor.singular} con ese nombre.", "danger")
        else:
            flash(
                f"Se registró “{nombre}” en {descriptor.titulo.lower()}.",
                "success",
            )
        return redirect(url_for("catalogos.listar", clave=clave))

    def editar(self, clave: str, registro_id: int):
        descriptor = self._descriptor_or_404(clave)
        registro = db.get_or_404(descriptor.modelo, registro_id)
        protegido = descriptor.es_protegido(registro)

        if request.method == "POST":
            nombre, error = None, None
            if not self.csrf.verify_token(request.form.get("csrf_token", "")):
                error = "La sesión expiró. Intenta nuevamente."
            elif protegido:
                error = "Este estatus lo usa el sistema y no se puede renombrar."
            else:
                nombre, error = self.service.validate_name(
                    descriptor,
                    request.form.get("nombre", ""),
                    registro,
                )
            if error is None:
                registro.nombre = nombre
                if descriptor.tiene_activo:
                    registro.activo = request.form.get("activo") == "1"
                try:
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()
                    error = f"Ya existe un {descriptor.singular} con ese nombre."
                else:
                    flash(f"Se actualizó “{nombre}”.", "success")
                    return redirect(url_for("catalogos.listar", clave=clave))
            flash(error, "danger")

        return render_template(
            "admin/catalogo_form.html",
            clave=clave,
            catalogo=descriptor,
            registro=registro,
            protegido=protegido,
            en_uso=self.service.usage_count(descriptor, registro.id),
        )

    def eliminar(self, clave: str, registro_id: int):
        descriptor = self._descriptor_or_404(clave)
        registro = db.get_or_404(descriptor.modelo, registro_id)
        if not self.csrf.verify_token(request.form.get("csrf_token", "")):
            flash("La sesión expiró. Intenta nuevamente.", "danger")
        elif descriptor.es_protegido(registro):
            flash("Este estatus lo usa el sistema y no se puede eliminar.", "danger")
        elif self.service.usage_count(descriptor, registro.id):
            sugerencia = (
                " Puedes desactivarlo en su lugar."
                if descriptor.tiene_activo
                else ""
            )
            flash(
                f"No se puede eliminar “{registro.nombre}” porque tiene solicitudes asociadas."
                + sugerencia,
                "danger",
            )
        else:
            nombre = registro.nombre
            db.session.delete(registro)
            db.session.commit()
            flash(f"Se eliminó “{nombre}”.", "success")
        return redirect(url_for("catalogos.listar", clave=clave))

    def create_blueprint(self, admin_required_decorator) -> Blueprint:
        bp = Blueprint("catalogos", __name__, url_prefix="/admin/catalogos")
        bp.add_url_rule(
            "/<clave>",
            endpoint="listar",
            view_func=admin_required_decorator(self.listar),
            methods=["GET"],
        )
        bp.add_url_rule(
            "/<clave>",
            endpoint="crear",
            view_func=admin_required_decorator(self.crear),
            methods=["POST"],
        )
        bp.add_url_rule(
            "/<clave>/<int:registro_id>/editar",
            endpoint="editar",
            view_func=admin_required_decorator(self.editar),
            methods=["GET", "POST"],
        )
        bp.add_url_rule(
            "/<clave>/<int:registro_id>/eliminar",
            endpoint="eliminar",
            view_func=admin_required_decorator(self.eliminar),
            methods=["POST"],
        )
        return bp

