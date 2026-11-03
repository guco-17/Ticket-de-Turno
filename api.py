from controllers.api_controller import ApiController

_api_controller = ApiController()
api = _api_controller.create_blueprint()

