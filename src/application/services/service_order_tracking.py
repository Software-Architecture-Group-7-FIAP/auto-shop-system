def build_service_order_tracking_url(frontend_public_url: str, service_order_id: int) -> str:
    base_url = frontend_public_url.rstrip("/")
    return f"{base_url}/track-service-order?serviceOrderId={service_order_id}"
