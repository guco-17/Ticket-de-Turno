from auth import admin_required
from controllers.catalogo_controller import CatalogoController
from models import Estatus
from patterns.factory import CatalogoFactory

_catalogo_controller = CatalogoController()
catalogos = _catalogo_controller.create_blueprint(admin_required)
ESTATUS_PROTEGIDOS = set(Estatus.ESTATUS_SISTEMA)
CATALOGOS = CatalogoFactory.todos()
