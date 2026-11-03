from functools import wraps

from flask import Blueprint, jsonify, make_response, request, session

from extensions import db
from models import Estatus, Municipio, Solicitud
from patterns.observer import auditoria_observer
from services.auth_service import AuthService, CsrfProtectionService
from services.dashboard_service import DashboardService
from services.solicitud_service import SolicitudService


class ApiController:
    """Controlador MVC orientado a objetos que implementa la estrategia de API REST (/api/v1)."""

    def __init__(
        self,
        solicitud_service: SolicitudService | None = None,
        dashboard_service: DashboardService | None = None,
        auth_service: AuthService | None = None,
        csrf_service: CsrfProtectionService | None = None,
    ):
        self.solicitud_service = solicitud_service or SolicitudService()
        self.dashboard_service = dashboard_service or DashboardService()
        self.csrf_service = csrf_service or CsrfProtectionService()
        self.auth_service = auth_service or AuthService(csrf_service=self.csrf_service)

    @staticmethod
    def _json_response(payload: dict, status_code: int = 200):
        response = make_response(jsonify(payload), status_code)
        response.headers["Cache-Control"] = "no-store, max-age=0"
        response.headers["Pragma"] = "no-cache"
        return response

    def api_admin_required(self, view):
        """Decorador para proteger recursos privados de la API REST con código 401 JSON."""

        @wraps(view)
        def wrapped_view(*args, **kwargs):
            if self.auth_service.get_active_admin() is None:
                session.clear()
                return self._json_response(
                    {"mensaje": "No autorizado. Inicia sesión como administrador."},
                    401,
                )
            return view(*args, **kwargs)

        return wrapped_view

    def _verify_csrf_header(self):
        token = request.headers.get("X-CSRF-Token", "")
        if not self.csrf_service.verify_token(token):
            return self._json_response(
                {
                    "mensaje": (
                        "Token CSRF inválido o vencido. Recarga la página e inténtalo nuevamente."
                    )
                },
                400,
            )
        return None

    # --- Recursos públicos REST ---

    def listar_municipios(self):
        """GET /api/v1/municipios — Lista los municipios activos."""
        municipios = (
            Municipio.query.filter_by(activo=True)
            .order_by(Municipio.nombre)
            .all()
        )
        return self._json_response(
            {
                "total": len(municipios),
                "municipios": [m.to_dict() for m in municipios],
            }
        )

    def obtener_solicitud_publica(self, curp: str, turno: int):
        """GET /api/v1/solicitudes/<curp>/<turno> — Consulta pública de solicitud por CURP y turno."""
        curp_validado, turno_validado, error = (
            self.solicitud_service.validator.validate_ticket_identity(
                {"curp": curp, "turno": turno}
            )
        )
        if error:
            return self._json_response({"mensaje": error}, 400)

        solicitud = self.solicitud_service.find_by_curp_and_turn(
            curp_validado, turno_validado
        )
        if solicitud is None:
            return self._json_response(
                {
                    "mensaje": (
                        "No encontramos una solicitud con ese CURP y número de turno."
                    )
                },
                404,
            )
        return self._json_response(solicitud.to_public_dict())

    # --- Recursos privados REST (Administración y Dashboard) ---

    def estadisticas_dashboard(self):
        """GET /api/v1/dashboard/estatus — Métricas de estatus filtradas por municipio o totales."""
        raw_municipio = (request.args.get("municipio_id") or "").strip()
        municipio_id = None
        if raw_municipio and raw_municipio.lower() != "all":
            try:
                municipio_id = int(raw_municipio)
            except ValueError:
                return self._json_response(
                    {"mensaje": "El identificador de municipio no es válido."},
                    400,
                )
            if municipio_id < 1:
                return self._json_response(
                    {"mensaje": "El identificador de municipio no es válido."},
                    400,
                )

        try:
            estadisticas = self.dashboard_service.obtener_estadisticas(
                municipio_id=municipio_id
            )
        except LookupError as exc:
            return self._json_response({"mensaje": str(exc)}, 404)

        return self._json_response(estadisticas)

    def listar_solicitudes(self):
        """GET /api/v1/solicitudes — Consulta y filtrado de solicitudes para administradores."""
        criterio = request.args.get("criterio", "nombre")
        if criterio not in self.solicitud_service.CRITERIOS_BUSQUEDA:
            criterio = "nombre"
        termino = request.args.get("q", "").strip()[:100]
        resultados = self.solicitud_service.search(criterio, termino)

        municipio_id = request.args.get("municipio_id", type=int)
        estatus_id = request.args.get("estatus_id", type=int)
        if municipio_id is not None:
            resultados = [s for s in resultados if s.municipio_id == municipio_id]
        if estatus_id is not None:
            resultados = [s for s in resultados if s.estatus_id == estatus_id]

        return self._json_response(
            {
                "total": len(resultados),
                "solicitudes": [s.to_dict() for s in resultados],
            }
        )

    def obtener_solicitud_admin(self, solicitud_id: int):
        """GET /api/v1/solicitudes/<id> — Detalle de una solicitud por ID."""
        solicitud = db.session.get(Solicitud, solicitud_id)
        if solicitud is None:
            return self._json_response(
                {"mensaje": "La solicitud solicitada no existe."},
                404,
            )
        return self._json_response(solicitud.to_dict())

    def actualizar_estatus_solicitud(self, solicitud_id: int):
        """PATCH /api/v1/solicitudes/<id>/estatus — Actualiza el estatus de una solicitud."""
        csrf_error = self._verify_csrf_header()
        if csrf_error is not None:
            return csrf_error

        solicitud = db.session.get(Solicitud, solicitud_id)
        if solicitud is None:
            return self._json_response(
                {"mensaje": "La solicitud solicitada no existe."},
                404,
            )

        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return self._json_response(
                {"mensaje": "El cuerpo de la petición debe ser un objeto JSON válido."},
                400,
            )

        estatus = None
        if "estatus_id" in payload:
            try:
                estatus_id = int(payload["estatus_id"])
            except (TypeError, ValueError):
                estatus_id = 0
            estatus = db.session.get(Estatus, estatus_id)
        elif "estatus" in payload:
            nombre_estatus = str(payload.get("estatus", "")).strip()
            if nombre_estatus:
                estatus = Estatus.query.filter_by(nombre=nombre_estatus).first()

        if estatus is None:
            return self._json_response(
                {"mensaje": "Selecciona un estatus válido."},
                400,
            )

        solicitud.estatus = estatus
        db.session.commit()
        self.solicitud_service.notify_event("estatus_actualizado_api", solicitud)
        return self._json_response(
            {
                "mensaje": (
                    f"La solicitud con CURP {solicitud.curp} ahora está “{estatus.nombre}”."
                ),
                "solicitud": solicitud.to_dict(),
            }
        )

    def eliminar_solicitud_api(self, solicitud_id: int):
        """DELETE /api/v1/solicitudes/<id> — Elimina una solicitud mediante la API REST."""
        csrf_error = self._verify_csrf_header()
        if csrf_error is not None:
            return csrf_error

        solicitud = db.session.get(Solicitud, solicitud_id)
        if solicitud is None:
            return self._json_response(
                {"mensaje": "La solicitud solicitada no existe."},
                404,
            )

        curp = solicitud.curp
        self.solicitud_service.notify_event("solicitud_eliminada_api", solicitud)
        db.session.delete(solicitud)
        db.session.commit()
        return self._json_response(
            {
                "mensaje": f"Se eliminó la solicitud con CURP {curp}.",
                "id": solicitud_id,
            }
        )

    def listar_auditoria(self):
        """GET /api/v1/auditoria — Bitácora de eventos capturados por el patrón Observer."""
        eventos = auditoria_observer.historial
        return self._json_response(
            {
                "total": len(eventos),
                "eventos": eventos,
            }
        )

    def create_blueprint(self) -> Blueprint:
        bp = Blueprint("api", __name__, url_prefix="/api/v1")
        bp.add_url_rule(
            "/municipios",
            endpoint="municipios",
            view_func=self.listar_municipios,
            methods=["GET"],
        )
        bp.add_url_rule(
            "/solicitudes/<string:curp>/<int:turno>",
            endpoint="solicitud_publica",
            view_func=self.obtener_solicitud_publica,
            methods=["GET"],
        )
        bp.add_url_rule(
            "/dashboard/estatus",
            endpoint="dashboard_estatus",
            view_func=self.api_admin_required(self.estadisticas_dashboard),
            methods=["GET"],
        )
        bp.add_url_rule(
            "/solicitudes",
            endpoint="solicitudes",
            view_func=self.api_admin_required(self.listar_solicitudes),
            methods=["GET"],
        )
        bp.add_url_rule(
            "/solicitudes/<int:solicitud_id>",
            endpoint="solicitud_detalle",
            view_func=self.api_admin_required(self.obtener_solicitud_admin),
            methods=["GET"],
        )
        bp.add_url_rule(
            "/solicitudes/<int:solicitud_id>/estatus",
            endpoint="actualizar_estatus",
            view_func=self.api_admin_required(self.actualizar_estatus_solicitud),
            methods=["PATCH"],
        )
        bp.add_url_rule(
            "/solicitudes/<int:solicitud_id>",
            endpoint="eliminar_solicitud",
            view_func=self.api_admin_required(self.eliminar_solicitud_api),
            methods=["DELETE"],
        )
        bp.add_url_rule(
            "/auditoria",
            endpoint="auditoria",
            view_func=self.api_admin_required(self.listar_auditoria),
            methods=["GET"],
        )
        return bp

