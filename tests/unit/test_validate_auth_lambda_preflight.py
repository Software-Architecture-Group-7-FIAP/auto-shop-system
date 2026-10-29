from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from subprocess import CompletedProcess

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / ".github" / "scripts" / "validate_auth_lambda_preflight.py"
SPEC = importlib.util.spec_from_file_location("validate_auth_lambda_preflight", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


ACCOUNT_ID = "123456789012"
HML_ARN = f"arn:aws:lambda:us-east-1:{ACCOUNT_ID}:function:customer-cpf-auth-homolog"
PRD_ARN = f"arn:aws:lambda:us-east-1:{ACCOUNT_ID}:function:customer-cpf-auth-prod"
VPC_ID = "vpc-0123456789abcdef0"
SUBNET_IDS = {"subnet-0123456789abcdef0", "subnet-1123456789abcdef0"}
SECURITY_GROUP_ID = "sg-0123456789abcdef0"


def _function_configuration(arn: str, *, stage: str, vpc_id: str = "vpc-0123456789abcdef0") -> dict[str, object]:
    environment = "homolog" if stage == "hml" else "prod"
    database_stage = "hml" if stage == "hml" else "prd"
    return {
        "FunctionName": arn.rsplit(":", 1)[-1],
        "FunctionArn": arn,
        "State": "Active",
        "LastUpdateStatus": "Successful",
        "VpcConfig": {
            "VpcId": vpc_id,
            "SubnetIds": sorted(SUBNET_IDS),
            "SecurityGroupIds": [SECURITY_GROUP_ID],
        },
        "DatabaseSecretId": f"auto-shop/staging/{database_stage}/lambda-auth",
    }


def _install_successful_aws_calls(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def run(command: list[str], **_kwargs: object) -> CompletedProcess[str]:
        calls.append(command)
        if command[1:3] == ["sts", "get-caller-identity"]:
            return CompletedProcess(command, 0, json.dumps({"Account": ACCOUNT_ID}), "")
        if command[1:3] == ["ssm", "get-parameters"]:
            return CompletedProcess(
                command,
                0,
                json.dumps(
                    {
                        "Parameters": [
                            {"Name": PREFLIGHT.SSM_PARAMETER_NAMES["hml"], "Type": "String", "Value": HML_ARN},
                            {"Name": PREFLIGHT.SSM_PARAMETER_NAMES["prd"], "Type": "String", "Value": PRD_ARN},
                            {"Name": PREFLIGHT.NETWORK_PARAMETER_NAMES["vpc_id"], "Type": "String", "Value": VPC_ID},
                            {
                                "Name": PREFLIGHT.NETWORK_PARAMETER_NAMES["private_subnet_ids"],
                                "Type": "StringList",
                                "Value": ",".join(sorted(SUBNET_IDS)),
                            },
                            {
                                "Name": PREFLIGHT.NETWORK_PARAMETER_NAMES["lambda_security_group_id"],
                                "Type": "String",
                                "Value": SECURITY_GROUP_ID,
                            },
                        ],
                        "InvalidParameters": [],
                    }
                ),
                "",
            )
        if command[1:3] == ["lambda", "get-function-configuration"]:
            arn = command[command.index("--function-name") + 1]
            stage = "hml" if arn == HML_ARN else "prd"
            configuration = _function_configuration(arn, stage=stage)
            return CompletedProcess(command, 0, json.dumps(configuration), "")
        raise AssertionError(f"unexpected AWS CLI command: {command[1:3]}")

    monkeypatch.setattr(PREFLIGHT.subprocess, "run", run)
    return calls


def test_preflight_accepts_both_active_private_auth_lambdas(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_successful_aws_calls(monkeypatch)

    PREFLIGHT.validate_auth_lambda_contract(ACCOUNT_ID)

    assert len(calls) == 4
    ssm_call = next(command for command in calls if command[1:3] == ["ssm", "get-parameters"])
    assert set(ssm_call[ssm_call.index("--names") + 1 : ssm_call.index("--region")]) == set(
        PREFLIGHT.ALL_PARAMETER_NAMES
    )
    lambda_calls = [command for command in calls if command[1:3] == ["lambda", "get-function-configuration"]]
    assert len(lambda_calls) == 2
    assert all(
        any("Environment.Variables.DATABASE_SECRET_ID" in argument for argument in command)
        for command in lambda_calls
    )


def test_preflight_rejects_lambda_outside_private_vpc(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_successful_aws_calls(monkeypatch)
    original_run = PREFLIGHT.subprocess.run

    def run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        if command[1:3] == ["lambda", "get-function-configuration"] and command[
            command.index("--function-name") + 1
        ] == PRD_ARN:
            return CompletedProcess(
                command,
                0,
                json.dumps(_function_configuration(PRD_ARN, stage="prd", vpc_id="")),
                "",
            )
        return original_run(command, **kwargs)

    monkeypatch.setattr(PREFLIGHT.subprocess, "run", run)

    with pytest.raises(PREFLIGHT.AuthLambdaPreflightError, match="PRD auth Lambda is not ready"):
        PREFLIGHT.validate_auth_lambda_contract(ACCOUNT_ID)


def test_preflight_rejects_lambda_attached_to_different_network_contract(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_successful_aws_calls(monkeypatch)
    original_run = PREFLIGHT.subprocess.run

    def run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        if command[1:3] == ["lambda", "get-function-configuration"] and command[
            command.index("--function-name") + 1
        ] == PRD_ARN:
            configuration = _function_configuration(PRD_ARN, stage="prd")
            configuration["VpcConfig"] = {
                "VpcId": "vpc-fffffffffffffffff",
                "SubnetIds": sorted(SUBNET_IDS),
                "SecurityGroupIds": [SECURITY_GROUP_ID],
            }
            return CompletedProcess(command, 0, json.dumps(configuration), "")
        return original_run(command, **kwargs)

    monkeypatch.setattr(PREFLIGHT.subprocess, "run", run)

    with pytest.raises(PREFLIGHT.AuthLambdaPreflightError, match="approved VPC"):
        PREFLIGHT.validate_auth_lambda_contract(ACCOUNT_ID)


def test_preflight_rejects_parameter_from_another_account(monkeypatch: pytest.MonkeyPatch) -> None:
    _install_successful_aws_calls(monkeypatch)
    successful_run = PREFLIGHT.subprocess.run

    def run(command: list[str], **kwargs: object) -> CompletedProcess[str]:
        if command[1:3] == ["ssm", "get-parameters"]:
            return CompletedProcess(
                command,
                0,
                json.dumps(
                    {
                        "Parameters": [
                            {"Name": PREFLIGHT.SSM_PARAMETER_NAMES["hml"], "Type": "String", "Value": HML_ARN},
                            {
                                "Name": PREFLIGHT.SSM_PARAMETER_NAMES["prd"],
                                "Type": "String",
                                "Value": PRD_ARN.replace(ACCOUNT_ID, "999999999999"),
                            },
                            {"Name": PREFLIGHT.NETWORK_PARAMETER_NAMES["vpc_id"], "Type": "String", "Value": VPC_ID},
                            {
                                "Name": PREFLIGHT.NETWORK_PARAMETER_NAMES["private_subnet_ids"],
                                "Type": "StringList",
                                "Value": ",".join(sorted(SUBNET_IDS)),
                            },
                            {
                                "Name": PREFLIGHT.NETWORK_PARAMETER_NAMES["lambda_security_group_id"],
                                "Type": "String",
                                "Value": SECURITY_GROUP_ID,
                            },
                        ],
                        "InvalidParameters": [],
                    }
                ),
                "",
            )
        return successful_run(command, **kwargs)

    monkeypatch.setattr(PREFLIGHT.subprocess, "run", run)

    with pytest.raises(PREFLIGHT.AuthLambdaPreflightError, match="PRD auth SSM contract is invalid"):
        PREFLIGHT.validate_auth_lambda_contract(ACCOUNT_ID)
