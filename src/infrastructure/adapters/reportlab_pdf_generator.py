from io import BytesIO
from reportlab.lib.pagesizes import A4  # Trocado de letter para A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from src.application.ports.pdf_generator import PdfGenerator
from typing import Any, Dict

class ReportLabPdfGenerator(PdfGenerator):
    def generate_budget_pdf(self, budget_data: Dict[str, Any]) -> bytes:
        buffer = BytesIO()
        
        # Ajustado para A4 (dimensões padrão no Brasil) e mantendo boas margens
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )
        story = []
        
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

        # 1. Título e Cabeçalho
        story.append(Paragraph(f"Orçamento #{budget_data.get('id')}", title_style))
        story.append(Spacer(1, 15))
        story.append(Paragraph(f"<b>Cliente:</b> {budget_data.get('customer_name')}", normal_style))
        story.append(Paragraph(f"<b>Placa:</b> {budget_data.get('vehicle_plate')}", normal_style))
        story.append(Spacer(1, 20))

        # 2. Montagem dos dados da Tabela
        # O total disponível para largura de tabela no A4 com margens 40 é ~515 pontos.
        # Ajustei as larguras para 385 e 130 para ocupar perfeitamente a largura total da página.
        table_data = [["Descrição", "Valor"]]
        for item in budget_data.get("items", []):
            table_data.append([item["description"], f"R$ {item['price']:.2f}"])
        
        table_data.append(["TOTAL", f"R$ {budget_data.get('total_value', 0.0):.2f}"])

        item_table = Table(table_data, colWidths=[385, 130])
        item_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (1, 0), colors.HexColor("#1A365D")),
            ('TEXTCOLOR', (0, 0), (1, 0), colors.whitesmoke),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),  # Alinha os valores da segunda coluna à direita
            ('ALIGN', (0, -1), (0, -1), 'RIGHT'), # NOVO: Alinha a palavra "TOTAL" à direita também
            ('FONTNAME', (0, 0), (1, 0), 'Helvetica-Bold'),
            ('BACKGROUND', (0, -1), (1, -1), colors.HexColor("#EDF2F7")),
            ('FONTNAME', (0, -1), (1, -1), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ]))
        
        story.append(item_table)
        
        # Renderização do documento
        doc.build(story)
        
        pdf_bytes = buffer.getvalue()
        buffer.close()
        
        return pdf_bytes
