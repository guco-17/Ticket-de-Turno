from services.receipt_service import QrCodeBuilder, TicketReceiptGenerator

_qr_builder = QrCodeBuilder()
_receipt_generator = TicketReceiptGenerator(qr_builder=_qr_builder)

NIVELES_EDUCATIVOS = TicketReceiptGenerator.NIVELES_EDUCATIVOS
ASUNTOS = TicketReceiptGenerator.ASUNTOS
create_curp_qr = _qr_builder.create_qr
build_ticket_receipt = _receipt_generator.build
