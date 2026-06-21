from typing import Protocol

from src.domain.budget.entity import Budget, BudgetProductLine, BudgetServiceLine


class BudgetRepository(Protocol):
    def add(self, budget: Budget) -> Budget:
        ...

    def get_by_id(self, budget_id: int) -> Budget | None:
        ...

    def get_by_approval_token(self, token: str) -> Budget | None:
        ...

    def list_all(self) -> list[Budget]:
        ...

    def add_service_line(self, line: BudgetServiceLine) -> BudgetServiceLine:
        ...

    def add_product_line(self, line: BudgetProductLine) -> BudgetProductLine:
        ...

    def get_product_line(
            self,
            budget_id: int,
            line_id: int,
    ) -> BudgetProductLine | None:
        ...

    def delete_product_line(self, line: BudgetProductLine) -> None:
        ...

    def save(self, budget: Budget) -> Budget:
        ...
