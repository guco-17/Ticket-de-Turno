from auth import admin_required
from controllers.admin_controller import AdminSolicitudesController

_admin_controller = AdminSolicitudesController()
admin = _admin_controller.create_blueprint(admin_required)
