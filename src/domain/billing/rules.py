from src.domain.exceptions import ValidationError
from src.domain.service_order.entity import ServiceOrder


def calculate_invoice_amount(service_order: ServiceOrder) -> float:
    service_total = sum(
        line.unit_price * line.quantity for line in service_order.service_lines
    )
    product_total = sum(
        line.unit_price * line.quantity for line in service_order.product_lines
    )
    return service_total + product_total


def validate_invoice_total_matches_lines(service_order: ServiceOrder) -> None:
    line_total = calculate_invoice_amount(service_order)
    if abs(line_total - service_order.total_price) > 0.01:
        raise ValidationError(
            "Total da OS diverge da soma dos itens: revise os valores antes da emissão da fatura"
        )


def validate_priced_lines(service_order: ServiceOrder) -> None:
    for line in service_order.service_lines:
        if line.unit_price is None or line.unit_price <= 0:
            raise ValidationError(
                "Itens sem precificação válida: revise os valores de venda "
                "dos serviços e produtos antes da emissão da fatura"
            )
    for line in service_order.product_lines:
        if line.unit_price is None or line.unit_price <= 0:
            raise ValidationError(
                "Itens sem precificação válida: revise os valores de venda "
                "dos serviços e produtos antes da emissão da fatura"
            )
