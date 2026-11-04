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
