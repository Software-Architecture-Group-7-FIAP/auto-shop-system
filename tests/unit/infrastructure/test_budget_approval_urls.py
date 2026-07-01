from src.infrastructure import budget_approval
from src.infrastructure.budget_approval import SettingsBudgetApprovalUrlBuilder


def test_budget_approval_urls_point_to_frontend_confirmation_page(monkeypatch):
    monkeypatch.setattr(
        budget_approval.settings,
        "frontend_public_url",
        "https://app.example.com/",
    )

    builder = SettingsBudgetApprovalUrlBuilder()

    assert builder.approve_url("token.with.dots") == (
        "https://app.example.com/budget-approval?token=token.with.dots&action=approve"
    )
    assert builder.reject_url("token.with.dots") == (
        "https://app.example.com/budget-approval?token=token.with.dots&action=reject"
    )


def test_budget_approval_urls_encode_token(monkeypatch):
    monkeypatch.setattr(
        budget_approval.settings,
        "frontend_public_url",
        "https://app.example.com",
    )

    builder = SettingsBudgetApprovalUrlBuilder()

    assert builder.approve_url("token+value") == (
        "https://app.example.com/budget-approval?token=token%2Bvalue&action=approve"
    )
