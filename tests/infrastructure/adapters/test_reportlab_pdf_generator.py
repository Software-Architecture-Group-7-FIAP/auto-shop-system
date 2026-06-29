from src.infrastructure.adapters.reportlab_pdf_generator import ReportLabPdfGenerator

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
