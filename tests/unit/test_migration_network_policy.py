from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
NETWORK_POLICIES = ROOT / "k8s" / "base" / "network" / "network-policy-strict.yaml"


def test_database_policies_allow_backend_migration_and_seed_clients() -> None:
    policies = yaml.safe_load_all(NETWORK_POLICIES.read_text(encoding="utf-8"))
    policies_by_name = {policy["metadata"]["name"]: policy for policy in policies}
    dns_egress = policies_by_name["allow-dns"]["spec"]["egress"][0]
    assert dns_egress["to"] == [
        {
            "namespaceSelector": {
                "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
            }
        }
    ]
    assert dns_egress["ports"] == [
        {"protocol": "UDP", "port": 53},
        {"protocol": "TCP", "port": 53},
    ]
    postgres_egress = policies_by_name["allow-rds-egress"]

    assert postgres_egress["spec"]["podSelector"] == {
        "matchExpressions": [
            {
                "key": "app.kubernetes.io/component",
                "operator": "In",
                "values": ["backend", "migrate", "seed"],
            }
        ]
    }
    assert postgres_egress["spec"]["egress"][0]["to"] == [
        {"podSelector": {"matchLabels": {"app.kubernetes.io/component": "database"}}}
    ]
    assert postgres_egress["spec"]["egress"][0]["ports"] == [
        {"protocol": "TCP", "port": 5432}
    ]

    postgres_ingress = policies_by_name["allow-postgres-ingress"]
    assert postgres_ingress["spec"]["podSelector"] == {
        "matchLabels": {"app.kubernetes.io/component": "database"}
    }
    assert postgres_ingress["spec"]["ingress"][0]["from"] == [
        {
            "podSelector": {
                "matchExpressions": [
                    {
                        "key": "app.kubernetes.io/component",
                        "operator": "In",
                        "values": ["backend", "migrate", "seed"],
                    }
                ]
            }
        }
    ]
    assert postgres_ingress["spec"]["ingress"][0]["ports"] == [
        {"protocol": "TCP", "port": 5432}
    ]


def test_kube_state_metrics_policies_only_allow_newrelic_infrastructure_scraper() -> None:
    policies = yaml.safe_load_all(NETWORK_POLICIES.read_text(encoding="utf-8"))
    policies_by_name = {policy["metadata"]["name"]: policy for policy in policies}
    ingress = policies_by_name["allow-kube-state-metrics-ingress"]
    egress = policies_by_name["allow-kube-state-metrics-egress"]
    scraper_selector = {"matchLabels": {"app.kubernetes.io/name": "newrelic-infrastructure"}}

    assert ingress["spec"]["ingress"][0]["from"] == [{"podSelector": scraper_selector}]
    assert egress["spec"]["podSelector"] == scraper_selector["matchLabels"]


def test_production_migration_overlay_enables_diagnostics() -> None:
    overlay = (
        ROOT / "k8s" / "overlays" / "production" / "migration" / "kustomization.yaml"
    ).read_text(encoding="utf-8")
    assert "MIGRATION_DIAGNOSTICS" in overlay
    assert 'value: "true"' in overlay
