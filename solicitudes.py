from services.solicitud_service import SolicitudValidator, TurnAllocatorService

_validator = SolicitudValidator()
_allocator = TurnAllocatorService()

NIVELES_EDUCATIVOS = _validator.NIVELES_EDUCATIVOS
ASUNTOS = _validator.ASUNTOS
CURP_PATTERN = _validator.CURP_PATTERN
validated_submission = _validator.validate_submission
allocate_turn = _allocator.allocate_turn
