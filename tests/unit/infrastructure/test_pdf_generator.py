from src.infrastructure.adapters.reportlab_pdf_generator import ReportLabPdfGenerator

def test_should_generate_pdf_bytes_successfully():
    # Arrange (Dados fictícios para o teste)
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

    # Act (Executa a geração do PDF)
    pdf_bytes = generator.generate_budget_pdf(budget_data)

    # Assert (Validações do teste)
    assert isinstance(pdf_bytes, bytes), "O retorno deve ser do tipo bytes"
    assert len(pdf_bytes) > 0, "O PDF gerado não pode estar vazio"
    
    # Validação mágica: os primeiros bytes de qualquer PDF válido no mundo sempre começam com b'%PDF'
    assert pdf_bytes.startswith(b'%PDF'), "O arquivo gerado não possui o cabeçalho válido de um PDF"

