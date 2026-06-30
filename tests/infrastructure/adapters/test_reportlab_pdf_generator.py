from src.infrastructure.adapters.reportlab_pdf_generator import ReportLabPdfGenerator
from src.infrastructure.pdf.generator import generate_service_order_pdf

def test_should_generate_pdf_bytes_successfully():
    # Arrange (Prepara a instância do adapter e dados fictícios do orçamento)
    generator = ReportLabPdfGenerator()
    budget_data = {
        "id": "2026-XYZ",
        "customer_name": "Cliente Teste S/A",
        "vehicle_plate": "BRA2E19",
        "items": [
            {"description": "Serviço de Alinhamento", "price": 100.00},
            {"description": "Pneu Aro 15", "price": 350.00}
        ],
        "total_value": 450.00
    }

    # Act (Executa a ação do adaptador de infraestrutura)
    pdf_bytes = generator.generate_budget_pdf(budget_data)

    # Assert (Garante que o comportamento técnico do adaptador está correto)
    assert isinstance(pdf_bytes, bytes), "O retorno do adapter deve ser estritamente em bytes"
    assert len(pdf_bytes) > 0, "O conteúdo do PDF gerado não pode estar vazio"
    assert pdf_bytes.startswith(b'%PDF'), "O cabeçalho gerado não corresponde a um arquivo PDF válido"


def test_should_generate_service_order_pdf_with_tracking_url_successfully():
    pdf_bytes = generate_service_order_pdf(
        os_id=1,
        customer_name="Cliente Teste",
        vehicle_plate="BRA2E19",
        status="Em diagnóstico",
        mechanic="Mecânico A",
        total_price=450.0,
        tracking_url="https://oficina.example.com/track-service-order?serviceOrderId=1",
    )

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")
