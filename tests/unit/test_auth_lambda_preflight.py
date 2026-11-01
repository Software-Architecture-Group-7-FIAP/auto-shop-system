import importlib.util
from pathlib import Path
from typing import Any

import pytest


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / ".github" / "scripts" / "validate_auth_lambda_preflight.py"
SPEC = importlib.util.spec_from_file_location("validate_auth_lambda_preflight", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
PREFLIGHT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREFLIGHT)


ACCOUNT_ID = "035611741563"
FUNCTION_ARN = f"arn:aws:lambda:us-east-1:{ACCOUNT_ID}:function:lambda-auth-hml"
PRD_FUNCTION_ARN = f"arn:aws:lambda:us-east-1:{ACCOUNT_ID}:function:lambda-auth-prd"
VPC_ID = "vpc-01234567"
SUBNET_IDS = ["subnet-01234567", "subnet-89abcdef"]
SECURITY_GROUP_ID = "sg-01234567"


def _parameters(function_arn: str = FUNCTION_ARN) -> dict[str, Any]:
    values = {
        PREFLIGHT.SSM_PARAMETER_NAMES["hml"]: {"Type": "String", "Value": function_arn},
        PREFLIGHT.SSM_PARAMETER_NAMES["prd"]: {"Type": "String", "Value": PRD_FUNCTION_ARN},
        PREFLIGHT.NETWORK_PARAMETER_NAMES["vpc_id"]: {"Type": "String", "Value": VPC_ID},
        PREFLIGHT.NETWORK_PARAMETER_NAMES["private_subnet_ids"]: {
            "Type": "StringList",
            "Value": ",".join(SUBNET_IDS),
        },
        PREFLIGHT.NETWORK_PARAMETER_NAMES["lambda_security_group_id"]: {
            "Type": "String",
            "Value": SECURITY_GROUP_ID,
        },
    }
    return {"Parameters": [{"Name": name, **parameter} for name, parameter in values.items()]}


def _configuration(function_arn: str = FUNCTION_ARN) -> dict[str, Any]:
    stage = "hml" if function_arn == FUNCTION_ARN else "prd"
    return {
        "FunctionArn": function_arn,
        "FunctionName": f"lambda-auth-{stage}",
        "State": "Active",
        "LastUpdateStatus": "Successful",
        "DatabaseSecretId": f"auto-shop/staging/{stage}/lambda-auth",
        "VpcConfig": {
            "VpcId": VPC_ID,
            "SubnetIds": SUBNET_IDS,
            "SecurityGroupIds": [SECURITY_GROUP_ID],
        },
    }


def test_preflight_reads_both_stage_arns_and_verifies_function_network_and_database_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_aws_json(*arguments: str) -> Any:
        calls.append(arguments)
        if arguments[:2] == ("sts", "get-caller-identity"):
            return {"Account": ACCOUNT_ID}
        if arguments[:2] == ("ssm", "get-parameters"):
            return _parameters()
        if arguments[:2] == ("lambda", "get-function-configuration"):
            return _configuration(arguments[arguments.index("--function-name") + 1])
        raise AssertionError(f"Unexpected AWS operation: {arguments[:2]}")

    monkeypatch.setattr(PREFLIGHT, "_aws_json", fake_aws_json)

    PREFLIGHT.validate_auth_lambda_contract(ACCOUNT_ID)

    ssm_call = next(arguments for arguments in calls if arguments[:2] == ("ssm", "get-parameters"))
    assert PREFLIGHT.SSM_PARAMETER_NAMES["hml"] in ssm_call
    assert PREFLIGHT.SSM_PARAMETER_NAMES["prd"] in ssm_call
    assert "--with-decryption" not in ssm_call
    lambda_calls = [
        arguments for arguments in calls if arguments[:2] == ("lambda", "get-function-configuration")
    ]
    assert len(lambda_calls) == 2
    assert {arguments[arguments.index("--function-name") + 1] for arguments in lambda_calls} == {
        FUNCTION_ARN,
        PRD_FUNCTION_ARN,
    }


def test_preflight_rejects_a_wrong_ssm_lambda_arn(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_aws_json(*arguments: str) -> Any:
        if arguments[:2] == ("sts", "get-caller-identity"):
            return {"Account": ACCOUNT_ID}
        if arguments[:2] == ("ssm", "get-parameters"):
            return _parameters(FUNCTION_ARN.replace("lambda-auth-hml", "lambda-auth-homolog"))
        raise AssertionError("The Lambda must not be queried when the SSM contract is invalid.")

    monkeypatch.setattr(PREFLIGHT, "_aws_json", fake_aws_json)

    with pytest.raises(PREFLIGHT.AuthLambdaPreflightError, match="SSM contract is invalid"):
        PREFLIGHT.validate_auth_lambda_contract(ACCOUNT_ID)
