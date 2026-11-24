"""Genera la constancia en PDF con folio, sello abreviado y código QR."""
import io

import qrcode
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

AZUL = (0.07, 0.30, 0.50)


def _qr(url):
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def constancia_pdf(datos, base_url):
    url = f"{base_url.rstrip('/')}/verificar/{datos['folio']}"
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    w, h = letter

    c.setFillColorRGB(*AZUL)
    c.rect(0, h - 3.2 * cm, w, 3.2 * cm, stroke=0, fill=1)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 20)
    c.drawString(2 * cm, h - 1.7 * cm, "Constancia de crédito complementario")
    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, h - 2.5 * cm, "Actividad deportiva · Plataforma digital (prototipo)")

    c.setFillColorRGB(0, 0, 0)
    c.setFont("Helvetica", 12)
    y = h - 5.2 * cm
    c.drawString(2 * cm, y, "Se hace constar que")
    c.setFont("Helvetica-Bold", 18)
    c.drawString(2 * cm, y - 1.0 * cm, datos["nombre"])
    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, y - 1.7 * cm, f"No. de control (simulado): {datos['no_control'] or '-'}")
    c.setFont("Helvetica", 12)
    c.drawString(2 * cm, y - 3.0 * cm, "cumplió con la actividad deportiva")
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, y - 3.8 * cm, f"{datos['actividad']}  ({datos['periodo']})")
    c.setFont("Helvetica", 12)
    c.drawString(2 * cm, y - 4.7 * cm, f"con una asistencia de {datos['porcentaje']:.0f} %.")

    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, y - 6.4 * cm, f"Autorizó: {datos['promotor']}")
    c.drawString(2 * cm, y - 7.0 * cm, f"Fecha de emisión: {datos['emitida_en']}")

    # Bloque de verificación
    c.setStrokeColorRGB(*AZUL)
    c.setLineWidth(1)
    c.rect(2 * cm, 3.0 * cm, w - 4 * cm, 5.2 * cm, stroke=1, fill=0)
    c.drawImage(_qr(url), 2.5 * cm, 3.4 * cm, 4.4 * cm, 4.4 * cm)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(7.4 * cm, 7.2 * cm, f"Folio: {datos['folio']}")
    c.setFont("Helvetica", 10)
    c.drawString(7.4 * cm, 6.5 * cm, "Verifica este documento escaneando el QR")
    c.drawString(7.4 * cm, 6.0 * cm, "o ingresando el folio en la página de verificación.")
    c.setFont("Courier", 8)
    c.drawString(7.4 * cm, 5.2 * cm, f"Sello: {datos['sello'][:32]}")
    c.drawString(7.4 * cm, 4.8 * cm, f"       {datos['sello'][32:]}")

    c.setFont("Helvetica-Oblique", 8)
    c.setFillColorRGB(0.35, 0.35, 0.35)
    c.drawString(2 * cm, 2.0 * cm, "Documento generado por un prototipo con datos simulados. "
                 "El sello digital detecta alteraciones; no sustituye una firma electrónica avanzada.")
    c.showPage()
    c.save()
    return buf.getvalue()
