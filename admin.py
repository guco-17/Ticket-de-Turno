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

from auth import admin_required, verify_csrf_token
from extensions import db
from models import Estatus, Municipio, Solicitud
from receipts import ASUNTOS as ASUNTO_LABELS
from receipts import NIVELES_EDUCATIVOS as NIVEL_LABELS
from solicitudes import allocate_turn, validated_submission


admin = Blueprint("admin", __name__, url_prefix="/admin")
CRITERIOS_BUSQUEDA = ("curp", "nombre")
LIMITE_RESULTADOS = 100


def _csrf_valid():
    return verify_csrf_token(request.form.get("csrf_token", ""))


def _redirect_back():
    target = request.form.get("next", "")
    if not target.startswith("/") or target.startswith("//") or "\\" in target:
        target = url_for("admin.solicitudes")
    return redirect(target)


def _like_pattern(term):
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _search_requests(criterio, termino):
    query = Solicitud.query
    if termino and criterio == "curp":
        query = query.filter(
            Solicitud.curp.like(_like_pattern(termino.upper()), escape="\\")
        )
    elif termino:
        for word in termino.split():
            pattern = _like_pattern(word)
            query = query.filter(
                db.or_(
                    Solicitud.nombre.ilike(pattern, escape="\\"),
                    Solicitud.apellido_paterno.ilike(pattern, escape="\\"),
                    Solicitud.apellido_materno.ilike(pattern, escape="\\"),
                )
            )
    return (
        query.order_by(Solicitud.creado_en.desc(), Solicitud.id.desc())
        .limit(LIMITE_RESULTADOS)
        .all()
    )


def _form_values(solicitud):
    return {
        "curp": solicitud.curp,
        "nombre": solicitud.nombre,
        "primer_apellido": solicitud.apellido_paterno,
        "segundo_apellido": solicitud.apellido_materno or "",
        "telefono_contacto": solicitud.telefono or "",
        "correo": solicitud.correo or "",
        "municipio": solicitud.municipio.nombre,
        "nivel_educativo": solicitud.nivel_educativo,
        "asunto": solicitud.asunto,
        "estatus_id": str(solicitud.estatus_id),
    }


def _render_form(solicitud, values):
    municipios = Municipio.query.filter(
        db.or_(
            Municipio.activo.is_(True),
            Municipio.id == (solicitud.municipio_id if solicitud else None),
        )
    ).order_by(Municipio.nombre).all()
    return render_template(
        "admin/solicitud_form.html",
        solicitud=solicitud,
        values=values,
        municipios=municipios,
        estatus=Estatus.query.order_by(Estatus.id).all(),
        niveles=NIVEL_LABELS,
        asuntos=ASUNTO_LABELS,
    )


def _save_request(solicitud):
    """Validate the submitted form and create or update a request."""
    if not _csrf_valid():
        flash("La sesión expiró. Intenta nuevamente.", "danger")
        return None, _render_form(solicitud, request.form)

    fields, error = validated_submission(request.form)
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
        return None, _render_form(solicitud, request.form)

    try:
        if solicitud is None:
            solicitud = Solicitud(
                municipio=municipio,
                turno=allocate_turn(municipio),
            )
            db.session.add(solicitud)
        elif solicitud.municipio_id != municipio.id:
            solicitud.turno = allocate_turn(municipio)
            solicitud.municipio = municipio

        solicitud.curp = fields["curp"]
        solicitud.nombre = fields["nombre"]
        solicitud.apellido_paterno = fields["apellido_paterno"]
        solicitud.apellido_materno = fields["apellido_materno"]
        solicitud.telefono = fields["telefono"]
        solicitud.correo = fields["correo"]
        solicitud.nivel_educativo = fields["nivel_educativo"]
        solicitud.asunto = fields["asunto"]
        solicitud.estatus = estatus
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("El registro cambió durante el guardado. Inténtalo nuevamente.", "danger")
        return None, _render_form(solicitud if solicitud and solicitud.id else None, request.form)
    except SQLAlchemyError:
        db.session.rollback()
        current_app.logger.exception("No se pudo guardar la solicitud desde administración.")
        flash("No fue posible guardar la solicitud. Inténtalo nuevamente.", "danger")
        return None, _render_form(solicitud if solicitud and solicitud.id else None, request.form)
    return solicitud, None


@admin.get("/solicitudes")
@admin_required
def solicitudes():
    criterio = request.args.get("criterio", "nombre")
    if criterio not in CRITERIOS_BUSQUEDA:
        criterio = "nombre"
    termino = request.args.get("q", "").strip()[:100]
    return render_template(
        "admin/solicitudes.html",
        solicitudes=_search_requests(criterio, termino),
        criterio=criterio,
        termino=termino,
        estatus=Estatus.query.order_by(Estatus.id).all(),
        niveles=NIVEL_LABELS,
        asuntos=ASUNTO_LABELS,
        limite=LIMITE_RESULTADOS,
    )


@admin.route("/solicitudes/nueva", methods=["GET", "POST"])
@admin_required
def nueva_solicitud():
    if request.method == "GET":
        pendiente = Estatus.query.filter_by(nombre="Pendiente").first()
        return _render_form(
            None,
            {"estatus_id": str(pendiente.id) if pendiente else ""},
        )
    solicitud, error_response = _save_request(None)
    if error_response is not None:
        return error_response
    flash(
        f"Solicitud registrada con el turno {solicitud.turno} "
        f"en {solicitud.municipio.nombre}.",
        "success",
    )
    return redirect(url_for("admin.solicitudes", criterio="curp", q=solicitud.curp))


@admin.route("/solicitudes/<int:solicitud_id>/editar", methods=["GET", "POST"])
@admin_required
def editar_solicitud(solicitud_id):
    solicitud = db.get_or_404(Solicitud, solicitud_id)
    if request.method == "GET":
        return _render_form(solicitud, _form_values(solicitud))
    solicitud, error_response = _save_request(solicitud)
    if error_response is not None:
        return error_response
    flash(f"Solicitud con CURP {solicitud.curp} actualizada.", "success")
    return redirect(url_for("admin.solicitudes", criterio="curp", q=solicitud.curp))


@admin.post("/solicitudes/<int:solicitud_id>/estatus")
@admin_required
def cambiar_estatus(solicitud_id):
    solicitud = db.get_or_404(Solicitud, solicitud_id)
    if not _csrf_valid():
        flash("La sesión expiró. Intenta nuevamente.", "danger")
        return redirect(url_for("admin.solicitudes"))
    estatus = db.session.get(Estatus, request.form.get("estatus_id", type=int) or 0)
    if estatus is None:
        flash("Selecciona un estatus válido.", "danger")
    else:
        solicitud.estatus = estatus
        db.session.commit()
        flash(
            f"La solicitud con CURP {solicitud.curp} ahora está “{estatus.nombre}”.",
            "success",
        )
    return _redirect_back()


@admin.post("/solicitudes/<int:solicitud_id>/eliminar")
@admin_required
def eliminar_solicitud(solicitud_id):
    solicitud = db.get_or_404(Solicitud, solicitud_id)
    if not _csrf_valid():
        flash("La sesión expiró. Intenta nuevamente.", "danger")
        return redirect(url_for("admin.solicitudes"))
    curp = solicitud.curp
    db.session.delete(solicitud)
    db.session.commit()
    flash(f"Se eliminó la solicitud con CURP {curp}.", "success")
    return _redirect_back()
