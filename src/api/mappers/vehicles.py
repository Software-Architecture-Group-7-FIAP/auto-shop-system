from src.api.schemas import VehicleResponse
from src.domain.vehicle.entity import Vehicle


def vehicle_to_response(vehicle: Vehicle) -> VehicleResponse:
    return VehicleResponse(
        id=vehicle.id,
        customer_id=vehicle.customer_id,
        plate=str(vehicle.plate),
        state=vehicle.state,
        city=vehicle.city,
        color=vehicle.color,
        brand=vehicle.brand,
        model=vehicle.model,
        year=vehicle.year,
        created_at=vehicle.created_at,
    )
