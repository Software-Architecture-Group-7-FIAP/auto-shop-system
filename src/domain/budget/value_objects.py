from src.domain.exceptions import ValidationError


class BudgetValidator:
    class ServiceLineValidator:
        @staticmethod
        def validate_quantity(quantity: int) -> int:
            if type(quantity) is not int:
                raise ValidationError("Quantidade deve ser um número inteiro")
            if quantity <= 0:
                raise ValidationError("Quantidade deve ser maior que zero")
            if quantity > 999_999:
                raise ValidationError("Quantidade muito grande, deve ser menor que 1.000.000")
            return quantity


    class ProductLineValidator:
        @staticmethod
        def validate_quantity(quantity: int) -> int:
            if type(quantity) is not int:
                raise ValidationError("Quantidade deve ser um número inteiro")
            if quantity <= 0:
                raise ValidationError("Quantidade deve ser maior que zero")
            if quantity > 999_999:
                raise ValidationError("Quantidade muito grande, deve ser menor que 1.000.000")
            return quantity

        @staticmethod
        def validate_existing_product(budget, product_id: int) -> None:
            if any(
                line.product_id == product_id and not line.from_service
                for line in budget.product_lines
            ):
                raise ValidationError("Este produto já foi adicionado ao orçamento")
