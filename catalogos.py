from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from sqlalchemy.exc import IntegrityError

from auth import admin_required, verify_csrf_token
from extensions import db
from models import Estatus, Municipio, Solicitud


catalogos = Blueprint("catalogos", __name__, url_prefix="/admin/catalogos")
# The application assigns "Pendiente" to new requests and the requirements
# depend on "Resuelto"; both must stay in the catalog with their names.
ESTATUS_PROTEGIDOS = {"Pendiente", "Resuelto"}
CATALOGOS = {
    "municipios": {
        "modelo": Municipio,
        "referencia": Solicitud.municipio_id,
        "titulo": "Municipios",
        "singular": "municipio",
        "longitud": 100,
        "tiene_activo": True,
    },
    "estatus": {
        "modelo": Estatus,
        "referencia": Solicitud.estatus_id,
        "titulo": "Estatus",
        "singular": "estatus",
        "longitud": 30,
        "tiene_activo": False,
    },
}


def _catalog_or_404(clave):
    catalogo = CATALOGOS.get(clave)
    if catalogo is None:
        abort(404)
    return catalogo


def _is_protected(catalogo, registro):
    return catalogo["modelo"] is Estatus and registro.nombre in ESTATUS_PROTEGIDOS


def _usage_count(catalogo, registro_id):
    return (
        db.session.query(db.func.count(Solicitud.id))
        .filter(catalogo["referencia"] == registro_id)
        .scalar()
    )


def _validated_name(catalogo, registro=None):
    nombre = " ".join(request.form.get("nombre", "").split())
    if not nombre:
        return None, "Escribe un nombre."
    if len(nombre) > catalogo["longitud"]:
        return None, f"El nombre admite como máximo {catalogo['longitud']} caracteres."
    modelo = catalogo["modelo"]
    duplicate = modelo.query.filter(
        db.func.lower(modelo.nombre) == nombre.lower(),
        modelo.id != (registro.id if registro else 0),
    ).first()
    if duplicate is not None:
        return None, f"Ya existe un {catalogo['singular']} con ese nombre."
    return nombre, None


@catalogos.get("/<clave>")
@admin_required
def listar(clave):
    catalogo = _catalog_or_404(clave)
    modelo = catalogo["modelo"]
    uso = dict(
        db.session.query(catalogo["referencia"], db.func.count(Solicitud.id))
        .group_by(catalogo["referencia"])
        .all()
    )
    return render_template(
        "admin/catalogo.html",
        clave=clave,
        catalogo=catalogo,
        registros=modelo.query.order_by(modelo.nombre).all(),
        uso=uso,
        protegidos=ESTATUS_PROTEGIDOS if modelo is Estatus else set(),
    )


@catalogos.post("/<clave>")
@admin_required
def crear(clave):
    catalogo = _catalog_or_404(clave)
    if not verify_csrf_token(request.form.get("csrf_token", "")):
        flash("La sesión expiró. Intenta nuevamente.", "danger")
        return redirect(url_for("catalogos.listar", clave=clave))
    nombre, error = _validated_name(catalogo)
    if error:
        flash(error, "danger")
        return redirect(url_for("catalogos.listar", clave=clave))

    registro = catalogo["modelo"](nombre=nombre)
    if catalogo["tiene_activo"]:
        registro.activo = request.form.get("activo") == "1"
    db.session.add(registro)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash(f"Ya existe un {catalogo['singular']} con ese nombre.", "danger")
    else:
        flash(f"Se registró “{nombre}” en {catalogo['titulo'].lower()}.", "success")
    return redirect(url_for("catalogos.listar", clave=clave))


@catalogos.route("/<clave>/<int:registro_id>/editar", methods=["GET", "POST"])
@admin_required
def editar(clave, registro_id):
    catalogo = _catalog_or_404(clave)
    registro = db.get_or_404(catalogo["modelo"], registro_id)
    protegido = _is_protected(catalogo, registro)
    if request.method == "POST":
        nombre, error = None, None
        if not verify_csrf_token(request.form.get("csrf_token", "")):
            error = "La sesión expiró. Intenta nuevamente."
        elif protegido:
            error = "Este estatus lo usa el sistema y no se puede renombrar."
        else:
            nombre, error = _validated_name(catalogo, registro)
        if error is None:
            registro.nombre = nombre
            if catalogo["tiene_activo"]:
                registro.activo = request.form.get("activo") == "1"
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error = f"Ya existe un {catalogo['singular']} con ese nombre."
            else:
                flash(f"Se actualizó “{nombre}”.", "success")
                return redirect(url_for("catalogos.listar", clave=clave))
        flash(error, "danger")
    return render_template(
        "admin/catalogo_form.html",
        clave=clave,
        catalogo=catalogo,
        registro=registro,
        protegido=protegido,
        en_uso=_usage_count(catalogo, registro.id),
    )


@catalogos.post("/<clave>/<int:registro_id>/eliminar")
@admin_required
def eliminar(clave, registro_id):
    catalogo = _catalog_or_404(clave)
    registro = db.get_or_404(catalogo["modelo"], registro_id)
    if not verify_csrf_token(request.form.get("csrf_token", "")):
        flash("La sesión expiró. Intenta nuevamente.", "danger")
    elif _is_protected(catalogo, registro):
        flash("Este estatus lo usa el sistema y no se puede eliminar.", "danger")
    elif _usage_count(catalogo, registro.id):
        sugerencia = " Puedes desactivarlo en su lugar." if catalogo["tiene_activo"] else ""
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
