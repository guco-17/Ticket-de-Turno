from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models import Estatus, Municipio, Solicitud
from services.auth_service import CsrfProtectionService
from services.receipt_service import TicketReceiptGenerator
from services.solicitud_service import SolicitudService


class AdminSolicitudesController:
    """Controlador MVC orientado a objetos para la gestión administrativa de solicitudes."""

    def __init__(
        self,
        solicitud_service: SolicitudService | None = None,
        csrf_service: CsrfProtectionService | None = None,
    ):
        self.service = solicitud_service or SolicitudService()
        self.csrf = csrf_service or CsrfProtectionService()

    def _csrf_valid(self) -> bool:
        return self.csrf.verify_token(request.form.get("csrf_token", ""))

    @staticmethod
    def _redirect_back():
        target = request.form.get("next", "")
        if not target.startswith("/") or target.startswith("//") or "\\" in target:
            target = url_for("admin.solicitudes")
        return redirect(target)

    @staticmethod
    def _form_values(solicitud: Solicitud) -> dict:
        values = solicitud.to_public_dict()
        values["estatus_id"] = str(solicitud.estatus_id)
        return values

    @staticmethod
    def _render_form(solicitud: Solicitud | None, values):
        municipios = (
            Municipio.query.filter(
                db.or_(
                    Municipio.activo.is_(True),
                    Municipio.id == (solicitud.municipio_id if solicitud else None),
                )
            )
            .order_by(Municipio.nombre)
            .all()
        )
        return render_template(
            "admin/solicitud_form.html",
            solicitud=solicitud,
            values=values,
            municipios=municipios,
            estatus=Estatus.query.order_by(Estatus.id).all(),
            niveles=TicketReceiptGenerator.NIVELES_EDUCATIVOS,
            asuntos=TicketReceiptGenerator.ASUNTOS,
        )

    def _save_request(self, solicitud: Solicitud | None):
        if not self._csrf_valid():
            flash("La sesión expiró. Intenta nuevamente.", "danger")
            return None, self._render_form(solicitud, request.form)

        fields, error = self.service.validator.validate_submission(request.form)
        estatus = None
        if error is None:
            estatus = db.session.get(
                Estatus,
                request.form.get("estatus_id", type=int) or 0,
            )
            if estatus is None:
                error = "Selecciona un estatus válido."
        municipio = None
        if error is None:
            municipio = Municipio.query.filter_by(nombre=fields["municipio"]).first()
            if municipio is None or (
                not municipio.activo
                and (solicitud is None or solicitud.municipio_id != municipio.id)
            ):
                error = "Selecciona un municipio disponible."
        if error is None:
            duplicate = Solicitud.query.filter(
                Solicitud.curp == fields["curp"],
                Solicitud.id != (solicitud.id if solicitud else 0),
            ).first()
            if duplicate is not None:
                error = "Ya existe otra solicitud registrada con ese CURP."
        if error:
            flash(error, "danger")
            return None, self._render_form(solicitud, request.form)

        es_nueva = solicitud is None
        try:
            if solicitud is None:
                solicitud = Solicitud(
                    municipio=municipio,
                    turno=self.service.turn_allocator.allocate_turn(municipio),
                )
                db.session.add(solicitud)
            elif solicitud.municipio_id != municipio.id:
                solicitud.turno = self.service.turn_allocator.allocate_turn(municipio)
                solicitud.municipio = municipio

            solicitud.actualizar_datos(fields)
            solicitud.estatus = estatus
            db.session.commit()
            self.service.notify_event(
                "solicitud_creada_admin" if es_nueva else "solicitud_editada_admin",
                solicitud,
            )
        except IntegrityError:
            db.session.rollback()
            flash("El registro cambió durante el guardado. Inténtalo nuevamente.", "danger")
            return (
                None,
                self._render_form(
                    solicitud if solicitud and solicitud.id else None,
                    request.form,
                ),
            )
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("No se pudo guardar la solicitud desde administración.")
            flash("No fue posible guardar la solicitud. Inténtalo nuevamente.", "danger")
            return (
                None,
                self._render_form(
                    solicitud if solicitud and solicitud.id else None,
                    request.form,
                ),
            )
        return solicitud, None

    def solicitudes(self):
        criterio = request.args.get("criterio", "nombre")
        if criterio not in self.service.CRITERIOS_BUSQUEDA:
            criterio = "nombre"
        termino = request.args.get("q", "").strip()[:100]
        return render_template(
            "admin/solicitudes.html",
            solicitudes=self.service.search(criterio, termino),
            criterio=criterio,
            termino=termino,
            estatus=Estatus.query.order_by(Estatus.id).all(),
            niveles=TicketReceiptGenerator.NIVELES_EDUCATIVOS,
            asuntos=TicketReceiptGenerator.ASUNTOS,
            limite=self.service.LIMITE_RESULTADOS,
        )

    def nueva_solicitud(self):
        if request.method == "GET":
            pendiente = Estatus.query.filter_by(nombre="Pendiente").first()
            return self._render_form(
                None,
                {"estatus_id": str(pendiente.id) if pendiente else ""},
            )
        solicitud, error_response = self._save_request(None)
        if error_response is not None:
            return error_response
        flash(
            f"Solicitud registrada con el turno {solicitud.turno} "
            f"en {solicitud.municipio.nombre}.",
            "success",
        )
        return redirect(url_for("admin.solicitudes", criterio="curp", q=solicitud.curp))

    def editar_solicitud(self, solicitud_id: int):
        solicitud = db.get_or_404(Solicitud, solicitud_id)
        if request.method == "GET":
            return self._render_form(solicitud, self._form_values(solicitud))
        solicitud, error_response = self._save_request(solicitud)
        if error_response is not None:
            return error_response
        flash(f"Solicitud con CURP {solicitud.curp} actualizada.", "success")
        return redirect(url_for("admin.solicitudes", criterio="curp", q=solicitud.curp))

    def cambiar_estatus(self, solicitud_id: int):
        solicitud = db.get_or_404(Solicitud, solicitud_id)
        if not self._csrf_valid():
            flash("La sesión expiró. Intenta nuevamente.", "danger")
            return redirect(url_for("admin.solicitudes"))
        estatus = db.session.get(Estatus, request.form.get("estatus_id", type=int) or 0)
        if estatus is None:
            flash("Selecciona un estatus válido.", "danger")
        else:
            solicitud.estatus = estatus
            db.session.commit()
            self.service.notify_event("estatus_actualizado", solicitud)
            flash(
                f"La solicitud con CURP {solicitud.curp} ahora está “{estatus.nombre}”.",
                "success",
            )
        return self._redirect_back()

    def eliminar_solicitud(self, solicitud_id: int):
        solicitud = db.get_or_404(Solicitud, solicitud_id)
        if not self._csrf_valid():
            flash("La sesión expiró. Intenta nuevamente.", "danger")
            return redirect(url_for("admin.solicitudes"))
        curp = solicitud.curp
        self.service.notify_event("solicitud_eliminada", solicitud)
        db.session.delete(solicitud)
        db.session.commit()
        flash(f"Se eliminó la solicitud con CURP {curp}.", "success")
        return self._redirect_back()

    def create_blueprint(self, admin_required_decorator) -> Blueprint:
        bp = Blueprint("admin", __name__, url_prefix="/admin")
        bp.add_url_rule(
            "/solicitudes",
            endpoint="solicitudes",
            view_func=admin_required_decorator(self.solicitudes),
            methods=["GET"],
        )
        bp.add_url_rule(
            "/solicitudes/nueva",
            endpoint="nueva_solicitud",
            view_func=admin_required_decorator(self.nueva_solicitud),
            methods=["GET", "POST"],
        )
        bp.add_url_rule(
            "/solicitudes/<int:solicitud_id>/editar",
            endpoint="editar_solicitud",
            view_func=admin_required_decorator(self.editar_solicitud),
            methods=["GET", "POST"],
        )
        bp.add_url_rule(
            "/solicitudes/<int:solicitud_id>/estatus",
            endpoint="cambiar_estatus",
            view_func=admin_required_decorator(self.cambiar_estatus),
            methods=["POST"],
        )
        bp.add_url_rule(
            "/solicitudes/<int:solicitud_id>/eliminar",
            endpoint="eliminar_solicitud",
            view_func=admin_required_decorator(self.eliminar_solicitud),
            methods=["POST"],
        )
        return bp

