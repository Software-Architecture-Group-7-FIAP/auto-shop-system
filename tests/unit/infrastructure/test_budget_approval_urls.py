from src.infrastructure import budget_approval
from src.infrastructure.budget_approval import SettingsBudgetApprovalUrlBuilder


def test_budget_approval_urls_point_to_frontend_confirmation_page(monkeypatch):
    monkeypatch.setattr(
        budget_approval.settings,
        "frontend_public_url",
        "https://app.example.com/",
    )

    builder = SettingsBudgetApprovalUrlBuilder()

    # The bearer token rides in the fragment: fragments are not sent in
    # Referer headers nor written to server access logs.
    assert builder.approve_url("token.with.dots") == (
        "https://app.example.com/budget-approval?action=approve#token.with.dots"
    )
    assert builder.reject_url("token.with.dots") == (
        "https://app.example.com/budget-approval?action=reject#token.with.dots"
    )


def test_budget_approval_urls_encode_token(monkeypatch):
    monkeypatch.setattr(
        budget_approval.settings,
        "frontend_public_url",
        "https://app.example.com",
    )

    builder = SettingsBudgetApprovalUrlBuilder()

    assert builder.approve_url("token+value") == (
        "https://app.example.com/budget-approval?action=approve#token%2Bvalue"
    )
