from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from src.application.ports.pdf_generator import PdfGenerator
from typing import Any, Dict

class ReportLabPdfGenerator(PdfGenerator):
    def generate_budget_pdf(self, budget_data: Dict[str, Any]) -> bytes:
        # Cria um buffer na memória RAM para guardar o PDF temporariamente
        buffer = BytesIO()
        
        # Configura o documento (tamanho da folha e margens)
        doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
        story = []
        
        # Define os estilos de texto
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'TitleStyle',
            parent=styles['Heading1'],
            fontSize=24,
            leading=28,
            textColor=colors.HexColor("#1A365D"),
            spaceAfter=20
        )
        normal_style = styles['Normal']

        # 1. Adiciona o Título e Cabeçalho do Orçamento
        story.append(Paragraph(f"Orçamento #{budget_data.get('id')}", title_style))
        story.append(Spacer(1, 15))
        story.append(Paragraph(f"<b>Cliente:</b> {budget_data.get('customer_name')}", normal_style))
        story.append(Paragraph(f"<b>Placa:</b> {budget_data.get('vehicle_plate')}", normal_style))
        story.append(Spacer(1, 20))

        # 2. Monta a Tabela de Itens e Valores
        table_data = [["Descrição", "Valor"]]
        for item in budget_data.get("items", []):
            table_data.append([item["description"], f"R$ {item['price']:.2f}"])
        
        # Linha com o Valor Total
        table_data.append(["TOTAL", f"R$ {budget_data.get('total_value', 0.0):.2f}"])

        # Estiliza a tabela (Cores, Alinhamentos e Bordas)
        item_table = Table(table_data, colWidths=[400, 130])
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0), colors.HexColor("#1A365D")), # Azul escuro no topo
            ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'), # Alinha preços à direita
            ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (1, -1), colors.HexColor("#EDF2F7")), # Fundo cinza no total
            ('FONTNAME', (0, -1), (1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        story.append(item_table)
        
        # Gera o PDF de fato
        doc.build(story)
        
        # Pega os bytes gerados e fecha o buffer
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
