from io import BytesIO

from flask import current_app, jsonify, render_template, request, send_file
from reportlab.platypus.doctemplate import LayoutError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from extensions import db
from models import Estatus, Municipio, Solicitud
from services.auth_service import CsrfProtectionService
from services.receipt_service import TicketReceiptGenerator
from services.solicitud_service import SolicitudService


class PublicController:
    """Controlador MVC orientado a objetos para el portal público de turnos."""

    def __init__(
        self,
        solicitud_service: SolicitudService | None = None,
        receipt_generator: TicketReceiptGenerator | None = None,
        csrf_service: CsrfProtectionService | None = None,
    ):
        self.solicitud_service = solicitud_service or SolicitudService()
        self.receipt_generator = receipt_generator or TicketReceiptGenerator()
        self.csrf_service = csrf_service or CsrfProtectionService()

    def _request_payload(self):
        if not self.csrf_service.verify_token(request.headers.get("X-CSRF-Token", "")):
            return None, (
                jsonify(
                    {
                        "mensaje": (
                            "La sesión expiró. Recarga la página e inténtalo nuevamente."
                        )
                    }
                ),
                400,
            )
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return None, (
                jsonify({"mensaje": "La solicitud no tiene un formato válido."}),
                400,
            )
        return payload, None

    @staticmethod
    def _active_municipalities():
        return (
            Municipio.query.filter_by(activo=True)
            .order_by(Municipio.nombre)
            .all()
        )

    def index(self):
        return render_template("index.html", municipios=self._active_municipalities())

    def welcome(self):
        return render_template("welcome.html")

    def solicitud(self):
        return render_template("index.html", municipios=self._active_municipalities())

    def buscar_solicitud(self):
        payload, error = self._request_payload()
        if error:
            return error
        curp, turno, validation_error = (
            self.solicitud_service.validator.validate_ticket_identity(payload)
        )
        if validation_error:
            return jsonify({"mensaje": validation_error}), 400

        solicitud = self.solicitud_service.find_by_curp_and_turn(curp, turno)
        if solicitud is None:
            return (
                jsonify(
                    {
                        "mensaje": (
                            "No encontramos una solicitud con ese CURP y número de turno."
                        )
                    }
                ),
                404,
            )
        return jsonify(solicitud.to_public_dict())

    def generar_turno(self):
        payload, error = self._request_payload()
        if error:
            return error
        fields, validation_error = (
            self.solicitud_service.validator.validate_submission(payload)
        )
        if validation_error:
            return jsonify({"mensaje": validation_error}), 400

        raw_turn = payload.get("turno")
        solicitud = None
        if raw_turn not in (None, ""):
            curp, turno, identity_error = (
                self.solicitud_service.validator.validate_ticket_identity(
                    {"curp": fields["curp"], "turno": raw_turn}
                )
            )
            if identity_error:
                return jsonify({"mensaje": identity_error}), 400
            solicitud = self.solicitud_service.find_by_curp_and_turn(
                curp, turno, for_update=True
            )
            if solicitud is None:
                return (
                    jsonify(
                        {
                            "mensaje": (
                                "No encontramos una solicitud con ese CURP y número de turno."
                            )
                        }
                    ),
                    404,
                )
            is_update = True
        else:
            if Solicitud.query.filter_by(curp=fields["curp"]).first() is not None:
                return (
                    jsonify(
                        {
                            "mensaje": (
                                "Ya existe una solicitud para ese CURP. Busca el registro "
                                "con su CURP y número de turno para modificarlo."
                            )
                        }
                    ),
                    409,
                )
            is_update = False

        municipio = Municipio.query.filter_by(
            nombre=fields["municipio"],
            activo=True,
        ).first()
        if municipio is None:
            return jsonify({"mensaje": "Selecciona un municipio disponible."}), 400
        estatus = Estatus.query.filter_by(nombre="Pendiente").first()
        if estatus is None:
            current_app.logger.error("No está registrado el estatus inicial Pendiente.")
            return (
                jsonify(
                    {
                        "mensaje": (
                            "El sistema no está configurado para recibir solicitudes."
                        )
                    }
                ),
                503,
            )

        try:
            if is_update:
                if solicitud.municipio_id != municipio.id:
                    solicitud.turno = (
                        self.solicitud_service.turn_allocator.allocate_turn(municipio)
                    )
                    solicitud.municipio = municipio
            else:
                solicitud = Solicitud(
                    municipio=municipio,
                    turno=self.solicitud_service.turn_allocator.allocate_turn(municipio),
                    curp=fields["curp"],
                    estatus_id=estatus.id,
                )
                db.session.add(solicitud)

            solicitud.actualizar_datos(fields)
            db.session.commit()
            db.session.refresh(solicitud)
            self.solicitud_service.notify_event(
                "solicitud_actualizada_publico"
                if is_update
                else "solicitud_creada_publico",
                solicitud,
            )
        except IntegrityError:
            db.session.rollback()
            return (
                jsonify(
                    {
                        "mensaje": (
                            "El registro cambió durante el guardado. "
                            "Recarga e inténtalo nuevamente."
                        )
                    }
                ),
                409,
            )
        except SQLAlchemyError:
            db.session.rollback()
            current_app.logger.exception("No se pudo guardar la solicitud pública.")
            return (
                jsonify(
                    {
                        "mensaje": (
                            "No fue posible guardar la solicitud. Inténtalo nuevamente."
                        )
                    }
                ),
                500,
            )

        try:
            pdf = self.receipt_generator.build(solicitud)
        except (LayoutError, OSError, TypeError, ValueError):
            current_app.logger.exception(
                "La solicitud %s se guardó, pero no se pudo generar el comprobante.",
                solicitud.id,
            )
            return (
                jsonify(
                    {
                        "mensaje": (
                            f"La solicitud se guardó con el turno {solicitud.turno}, "
                            "pero no se pudo generar el comprobante. Contacta al área de atención."
                        ),
                        "turno": solicitud.turno,
                        "municipio": solicitud.municipio.nombre,
                    }
                ),
                500,
            )

        filename = f"comprobante-turno-{solicitud.turno}.pdf"
        response = send_file(
            BytesIO(pdf),
            mimetype="application/pdf",
            as_attachment=True,
            download_name=filename,
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Turno-Asignado"] = str(solicitud.turno)
        response.headers["X-Registro-Actualizado"] = str(is_update).lower()
        return response

    def register_routes(self, app) -> None:
        app.add_url_rule("/", endpoint="index", view_func=self.index, methods=["GET"])
        app.add_url_rule(
            "/welcome", endpoint="welcome", view_func=self.welcome, methods=["GET"]
        )
        app.add_url_rule(
            "/solicitud", endpoint="solicitud", view_func=self.solicitud, methods=["GET"]
        )
        app.add_url_rule(
            "/buscar-solicitud",
            endpoint="buscar_solicitud",
            view_func=self.buscar_solicitud,
            methods=["POST"],
        )
        app.add_url_rule(
            "/generar-turno",
            endpoint="generar_turno",
            view_func=self.generar_turno,
            methods=["POST"],
        )

