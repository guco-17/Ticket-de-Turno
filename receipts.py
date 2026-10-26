from io import BytesIO
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.doctemplate import LayoutError

import qrcode
from qrcode.constants import ERROR_CORRECT_M

NIVELES_EDUCATIVOS = {
    "preescolar": "Preescolar",
    "kinder": "Kínder",
    "primaria": "Primaria",
    "secundaria": "Secundaria",
    "bachillerato": "Bachillerato",
    "licenciatura": "Licenciatura",
    "maestria": "Maestría",
    "doctorado": "Doctorado",
}
ASUNTOS = {
    "inscripcion": "Inscripción",
    "reinscripcion": "Reinscripción",
    "cambio_escuela": "Cambio de escuela",
    "duplicado_certificado": "Duplicado de certificado",
    "aclaracion_datos": "Aclaración de datos",
}


def create_curp_qr(curp):
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=8,
        border=4,
    )
    qr.add_data(curp)
    qr.make(fit=True)
    return qr


def _curp_qr_image(curp):
    qr = create_curp_qr(curp)
    image_buffer = BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(
        image_buffer,
        format="PNG",
    )
    image_buffer.seek(0)
    image = Image(image_buffer, width=35 * mm, height=35 * mm)
    image.hAlign = "CENTER"
    return image, image_buffer


def build_ticket_receipt(solicitud):
    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=letter,
        rightMargin=22 * mm,
        leftMargin=22 * mm,
        topMargin=22 * mm,
        bottomMargin=22 * mm,
        title=f"Comprobante de turno {solicitud.turno}",
        author="Sistema de Ticket de Turno",
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "ReceiptTitle",
        parent=styles["Title"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#5b2c6f"),
        fontSize=18,
        leading=23,
        spaceAfter=6 * mm,
    )
    subtitle_style = ParagraphStyle(
        "ReceiptSubtitle",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        textColor=colors.HexColor("#59636e"),
        fontSize=10,
        leading=14,
        spaceAfter=8 * mm,
    )
    label_style = ParagraphStyle(
        "ReceiptLabel",
        parent=styles["Normal"],
        textColor=colors.HexColor("#5b2c6f"),
        fontSize=9,
        leading=12,
    )
    value_style = ParagraphStyle(
        "ReceiptValue",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
    )

    full_name = " ".join(
        part
        for part in (
            solicitud.nombre,
            solicitud.apellido_paterno,
            solicitud.apellido_materno,
        )
        if part
    )
    created_at = (
        solicitud.creado_en.strftime("%d/%m/%Y %H:%M")
        if solicitud.creado_en
        else "Fecha no disponible"
    )
    rows = [
        ("Folio de solicitud", str(solicitud.id)),
        ("Número de turno", str(solicitud.turno)),
        ("Municipio de atención", solicitud.municipio.nombre),
        ("Nombre del solicitante", full_name),
        ("CURP", solicitud.curp),
        ("Teléfono", solicitud.telefono or "No proporcionado"),
        ("Correo electrónico", solicitud.correo or "No proporcionado"),
        (
            "Nivel educativo",
            NIVELES_EDUCATIVOS.get(
                solicitud.nivel_educativo,
                solicitud.nivel_educativo,
            ),
        ),
        (
            "Trámite solicitado",
            ASUNTOS.get(solicitud.asunto, solicitud.asunto),
        ),
        ("Fecha de registro", created_at),
    ]
    table_data = [
        [
            Paragraph(escape(label), label_style),
            Paragraph(escape(value), value_style),
        ]
        for label, value in rows
    ]
    details = Table(table_data, colWidths=(52 * mm, 106 * mm), hAlign="LEFT")
    details.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f2edf5")),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d9d2df")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 9),
                ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story = [
        Paragraph("Comprobante de solicitud de turno", title_style),
        Paragraph(
            "Conserva este comprobante. Para consultar o modificar la solicitud "
            "en el portal público necesitarás el CURP y el número de turno.",
            subtitle_style,
        ),
        details,
        Spacer(1, 8 * mm),
        Paragraph("Código QR de identificación del alumno (CURP)", subtitle_style),
    ]
    qr_image, qr_buffer = _curp_qr_image(solicitud.curp)
    story.extend(
        [
            qr_image,
            Spacer(1, 6 * mm),
            Paragraph(
                "Este documento confirma el registro de la solicitud en el sistema; "
                "no sustituye una resolución ni acredita la conclusión del trámite.",
                styles["Italic"],
            ),
        ]
    )
    try:
        document.build(story)
    finally:
        qr_buffer.close()
    return output.getvalue()
