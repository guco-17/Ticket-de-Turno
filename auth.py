from controllers.auth_controller import AuthController

_auth_controller = AuthController()
auth = _auth_controller.create_blueprint()

get_csrf_token = _auth_controller.csrf_service.get_token
verify_csrf_token = _auth_controller.csrf_service.verify_token
_digest_captcha = _auth_controller.captcha_service.digest
admin_required = _auth_controller.admin_required
