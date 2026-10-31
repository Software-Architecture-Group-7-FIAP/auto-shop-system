def build_service_order_tracking_url(frontend_public_url: str, token: str) -> str:
    base_url = frontend_public_url.rstrip("/")
    return f"{base_url}/track-service-order#{token}"
