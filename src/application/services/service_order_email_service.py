from sqlalchemy.orm import Session

from src.domain.exceptions import NotFoundError
from src.infrastructure.database import CustomerModel, ServiceOrderModel, VehicleModel
from src.infrastructure.email.service import send_email
from src.infrastructure.pdf.generator import generate_service_order_pdf


class ServiceOrderEmailService:
    def __init__(self, db: Session):
        self.db = db

    async def send_os_email(self, service_order_id: int) -> None:
        os = self.db.query(ServiceOrderModel).filter(ServiceOrderModel.id == service_order_id).first()
        if not os:
            raise NotFoundError("OS não encontrada")
        customer = self.db.query(CustomerModel).filter(CustomerModel.id == os.customer_id).first()
        vehicle = self.db.query(VehicleModel).filter(VehicleModel.id == os.vehicle_id).first()

        generate_service_order_pdf(
            os.id,
            customer.name if customer else "",
            vehicle.plate if vehicle else "",
            os.status.value,
            os.mechanic_name,
            os.total_price,
        )
        await send_email(
            customer.email,
            f"Ordem de Serviço #{os.id}",
            f"Sua OS #{os.id} está com status: {os.status.value}",
        )
