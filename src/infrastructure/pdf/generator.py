from io import BytesIO
import textwrap

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas


def _draw_wrapped_text(
    c: canvas.Canvas,
    x: float,
    y: float,
    text: str,
    width: int = 90,
    line_height: float = 0.45 * cm,
) -> float:
    for line in textwrap.wrap(text, width=width) or [""]:
        c.drawString(x, y, line)
        y -= line_height
    return y


def generate_budget_pdf(
    budget_id: int,
    customer_name: str,
    vehicle_plate: str,
    service_lines: list[dict],
    product_lines: list[dict],
    total_price: float,
) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 2 * cm

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, y, f"Orçamento #{budget_id}")
    y -= 1 * cm
    c.setFont("Helvetica", 12)
    c.drawString(2 * cm, y, f"Cliente: {customer_name}")
    y -= 0.7 * cm
    c.drawString(2 * cm, y, f"Veículo: {vehicle_plate}")
    y -= 1.2 * cm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Serviços")
    y -= 0.7 * cm
    c.setFont("Helvetica", 10)
    for line in service_lines:
        c.drawString(2 * cm, y, f"- {line['name']} x{line['quantity']}: R$ {line['total']:.2f}")
        y -= 0.5 * cm

    y -= 0.5 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Produtos")
    y -= 0.7 * cm
    c.setFont("Helvetica", 10)
    for line in product_lines:
        c.drawString(2 * cm, y, f"- {line['name']} x{line['quantity']}: R$ {line['total']:.2f}")
        y -= 0.5 * cm

    y -= 0.5 * cm
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, y, f"Total: R$ {total_price:.2f}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()


def generate_service_order_pdf(
    os_id: int,
    customer_name: str,
    vehicle_plate: str,
    status: str,
    mechanic: str | None,
    total_price: float,
    tracking_url: str,
) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    height = A4[1]
    y = height - 2 * cm

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, y, f"Ordem de Serviço #{os_id}")
    y -= 1 * cm
    c.setFont("Helvetica", 12)
    c.drawString(2 * cm, y, f"Cliente: {customer_name}")
    y -= 0.7 * cm
    c.drawString(2 * cm, y, f"Veículo: {vehicle_plate}")
    y -= 0.7 * cm
    c.drawString(2 * cm, y, f"Status: {status}")
    y -= 0.7 * cm
    if mechanic:
        c.drawString(2 * cm, y, f"Mecânico: {mechanic}")
        y -= 0.7 * cm
    c.drawString(2 * cm, y, f"Total: R$ {total_price:.2f}")
    y -= 1.2 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Acompanhamento")
    y -= 0.7 * cm
    c.setFont("Helvetica", 10)
    y = _draw_wrapped_text(c, 2 * cm, y, tracking_url)
    c.drawString(2 * cm, y, "Informe seu CPF/CNPJ para consultar o progresso.")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer.read()
