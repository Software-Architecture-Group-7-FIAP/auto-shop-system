from abc import ABC, abstractmethod
from typing import Any, Dict

class PdfGenerator(ABC):
    @abstractmethod
    def generate_budget_pdf(self, budget_data: Dict[str, Any]) -> bytes:
        """Gera o PDF do orçamento e retorna os bytes do arquivo."""
        pass
