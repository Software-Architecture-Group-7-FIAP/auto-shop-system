from typing import Protocol

from src.domain.budget.entity import Budget, BudgetProductLine, BudgetServiceLine


class BudgetRepository(Protocol):
    def add(self, budget: Budget) -> Budget:
        ...

    def get_by_id(self, budget_id: int) -> Budget | None:
        ...

    def get_by_approval_token_fingerprint(self, token_fingerprint: str) -> Budget | None:
        ...

    def list_all(self) -> list[Budget]:
        ...

    def list_revision_family(self, budget_id: int) -> list[Budget]:
        """Return every revision linked to the given one, ancestors included."""
        ...

    def add_service_line(self, line: BudgetServiceLine) -> BudgetServiceLine:
        ...

    def get_all_service_lines(self, budget_id: int) -> list[BudgetServiceLine]:
        ...

    def get_service_line(self, budget_id: int, service_id: int) -> BudgetServiceLine | None:
        ...

    def update_service_line(self, line: BudgetServiceLine) -> BudgetServiceLine:
        ...

    def delete_service_line(self, line: BudgetServiceLine) -> None:
        ...

    def add_product_line(self, line: BudgetProductLine) -> BudgetProductLine:
        ...

    def get_all_product_lines(self, budget_id: int) -> list[BudgetProductLine]:
        ...

    def get_product_line(self, budget_id: int, line_id: int) -> BudgetProductLine | None:
        ...

    def update_product_line(self, line: BudgetProductLine) -> BudgetProductLine:
        ...

    def delete_product_line(self, line: BudgetProductLine) -> None:
        ...

    def save(self, budget: Budget) -> Budget:
        ...
