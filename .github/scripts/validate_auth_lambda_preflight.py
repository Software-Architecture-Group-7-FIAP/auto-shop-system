#!/usr/bin/env python3
"""Check persistent customer-auth Lambdas before starting session resources."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any


AWS_REGION = "us-east-1"
SSM_PARAMETER_NAMES = {
    "hml": "/auto-shop/staging/auth/customer-token/function-arn/hml",
    "prd": "/auto-shop/staging/auth/customer-token/function-arn/prd",
}
NETWORK_PARAMETER_NAMES = {
    "vpc_id": "/auto-shop/staging/network/vpc-id",
    "private_subnet_ids": "/auto-shop/staging/network/workload-private-subnet-ids",
    "lambda_security_group_id": "/auto-shop/staging/network/lambda-security-group-id",
}
ALL_PARAMETER_NAMES = (*SSM_PARAMETER_NAMES.values(), *NETWORK_PARAMETER_NAMES.values())
DATABASE_SECRET_IDS = {
    "hml": "auto-shop/staging/hml/lambda-auth",
    "prd": "auto-shop/staging/prd/lambda-auth",
}
LAMBDA_ENVIRONMENTS = {"hml": "hml", "prd": "prd"}
ACCOUNT_ID_PATTERN = re.compile(r"^[0-9]{12}$")
VPC_ID_PATTERN = re.compile(r"^vpc-[0-9a-f]{8,17}$")
SUBNET_ID_PATTERN = re.compile(r"^subnet-[0-9a-f]{8,17}$")
SECURITY_GROUP_ID_PATTERN = re.compile(r"^sg-[0-9a-f]{8,17}$")

LAMBDA_CONFIGURATION_QUERY = (
    "{FunctionName:FunctionName,FunctionArn:FunctionArn,State:State,"
    "LastUpdateStatus:LastUpdateStatus,VpcConfig:VpcConfig,"
    "DatabaseSecretId:Environment.Variables.DATABASE_SECRET_ID}"
)


class AuthLambdaPreflightError(RuntimeError):
    """Raised when a persistent customer-auth Lambda is not safe to depend on."""


def _aws_json(*arguments: str) -> Any:
    try:
        result = subprocess.run(
            ["aws", *arguments],
            check=False,
            capture_output=True,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise AuthLambdaPreflightError("AWS read-only auth preflight could not complete.") from error

    if result.returncode != 0:
        raise AuthLambdaPreflightError("AWS read-only auth preflight returned an error.")
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise AuthLambdaPreflightError("AWS read-only auth preflight returned invalid JSON.") from error


def _expected_function_arn(value: object, *, stage: str, account_id: str) -> bool:
    if not isinstance(value, str):
        return False
    environment = LAMBDA_ENVIRONMENTS[stage]
    pattern = (
        rf"^arn:aws:lambda:{re.escape(AWS_REGION)}:{re.escape(account_id)}:"
        rf"function:[A-Za-z0-9_-]+-{environment}$"
    )
    return re.fullmatch(pattern, value) is not None


def _verify_function_configuration(
    configuration: Any,
    *,
    stage: str,
    function_arn: str,
    expected_vpc_id: str,
    expected_subnet_ids: set[str],
    expected_security_group_ids: set[str],
) -> None:
    stage_name = stage.upper()
    if not isinstance(configuration, dict):
        raise AuthLambdaPreflightError(f"{stage_name} auth Lambda is not ready.")

    vpc = configuration.get("VpcConfig")
    subnet_ids = vpc.get("SubnetIds") if isinstance(vpc, dict) else None
    security_group_ids = vpc.get("SecurityGroupIds") if isinstance(vpc, dict) else None
    matches_approved_network = (
        isinstance(vpc, dict)
        and vpc.get("VpcId") == expected_vpc_id
        and isinstance(subnet_ids, list)
        and all(isinstance(value, str) for value in subnet_ids)
        and len(subnet_ids) == len(set(subnet_ids))
        and set(subnet_ids) == expected_subnet_ids
        and isinstance(security_group_ids, list)
        and all(isinstance(value, str) for value in security_group_ids)
        and len(security_group_ids) == len(set(security_group_ids))
        and set(security_group_ids) == expected_security_group_ids
    )
    expected_function_name = function_arn.rsplit(":", 1)[-1]
    if (
        configuration.get("FunctionArn") != function_arn
        or configuration.get("FunctionName") != expected_function_name
        or configuration.get("State") != "Active"
        or configuration.get("LastUpdateStatus") != "Successful"
        or configuration.get("DatabaseSecretId") != DATABASE_SECRET_IDS[stage]
        or not matches_approved_network
    ):
        raise AuthLambdaPreflightError(
            f"{stage_name} auth Lambda is not ready (check its state, approved VPC, and database contract)."
        )


def _read_network_contract(by_name: dict[str, dict[str, Any]]) -> tuple[str, set[str], set[str]]:
    vpc_parameter = by_name.get(NETWORK_PARAMETER_NAMES["vpc_id"])
    subnet_parameter = by_name.get(NETWORK_PARAMETER_NAMES["private_subnet_ids"])
    security_group_parameter = by_name.get(NETWORK_PARAMETER_NAMES["lambda_security_group_id"])
    if (
        not isinstance(vpc_parameter, dict)
        or vpc_parameter.get("Type") != "String"
        or not isinstance(vpc_parameter.get("Value"), str)
        or not VPC_ID_PATTERN.fullmatch(vpc_parameter["Value"])
    ):
        raise AuthLambdaPreflightError("The upstream VPC contract is invalid; auth preflight stopped.")
    if (
        not isinstance(subnet_parameter, dict)
        or subnet_parameter.get("Type") != "StringList"
        or not isinstance(subnet_parameter.get("Value"), str)
    ):
        raise AuthLambdaPreflightError("The upstream private subnet contract is invalid; auth preflight stopped.")
    subnet_ids = [value.strip() for value in subnet_parameter["Value"].split(",")]
    if (
        not subnet_ids
        or any(not SUBNET_ID_PATTERN.fullmatch(value) for value in subnet_ids)
        or len(subnet_ids) != len(set(subnet_ids))
    ):
        raise AuthLambdaPreflightError("The upstream private subnet contract is invalid; auth preflight stopped.")
    if (
        not isinstance(security_group_parameter, dict)
        or security_group_parameter.get("Type") != "String"
        or not isinstance(security_group_parameter.get("Value"), str)
        or not SECURITY_GROUP_ID_PATTERN.fullmatch(security_group_parameter["Value"])
    ):
        raise AuthLambdaPreflightError("The upstream Lambda security group contract is invalid; auth preflight stopped.")
    return vpc_parameter["Value"], set(subnet_ids), {security_group_parameter["Value"]}


def validate_auth_lambda_contract(expected_account_id: str, stage: str | None = None) -> None:
    if not ACCOUNT_ID_PATTERN.fullmatch(expected_account_id):
        raise AuthLambdaPreflightError("EXPECTED_AWS_ACCOUNT_ID must contain exactly 12 digits.")
    if stage is not None and stage not in SSM_PARAMETER_NAMES:
        raise AuthLambdaPreflightError("The auth preflight stage must be hml or prd.")

    stages = tuple(SSM_PARAMETER_NAMES) if stage is None else (stage,)
    parameter_names = (
        *(SSM_PARAMETER_NAMES[current_stage] for current_stage in stages),
        *NETWORK_PARAMETER_NAMES.values(),
    )

    identity = _aws_json("sts", "get-caller-identity", "--output", "json")
    if not isinstance(identity, dict) or identity.get("Account") != expected_account_id:
        raise AuthLambdaPreflightError("Auth preflight resolved to an unexpected AWS account.")

    parameters = _aws_json(
        "ssm",
        "get-parameters",
        "--names",
        *parameter_names,
        "--region",
        AWS_REGION,
        "--output",
        "json",
    )
    if not isinstance(parameters, dict) or parameters.get("InvalidParameters"):
        raise AuthLambdaPreflightError("One or more required stage auth Lambda SSM contracts are absent.")

    parameter_items = parameters.get("Parameters")
    if not isinstance(parameter_items, list):
        raise AuthLambdaPreflightError("The auth Lambda SSM response is malformed.")
    by_name = {
        item.get("Name"): item
        for item in parameter_items
        if isinstance(item, dict) and isinstance(item.get("Name"), str)
    }
    if len(by_name) != len(parameter_names):
        raise AuthLambdaPreflightError("The auth and network SSM response is incomplete or ambiguous.")

    expected_vpc_id, expected_subnet_ids, expected_security_group_ids = _read_network_contract(by_name)

    for current_stage in stages:
        parameter_name = SSM_PARAMETER_NAMES[current_stage]
        parameter = by_name.get(parameter_name)
        if (
            not isinstance(parameter, dict)
            or parameter.get("Type") != "String"
            or not _expected_function_arn(
                parameter.get("Value"), stage=current_stage, account_id=expected_account_id
            )
        ):
            raise AuthLambdaPreflightError(
                f"{current_stage.upper()} auth SSM contract is invalid for this account and region."
            )

        function_arn = parameter["Value"]
        configuration = _aws_json(
            "lambda",
            "get-function-configuration",
            "--function-name",
            function_arn,
            "--region",
            AWS_REGION,
            "--query",
            LAMBDA_CONFIGURATION_QUERY,
            "--output",
            "json",
        )
        _verify_function_configuration(
            configuration,
            stage=current_stage,
            function_arn=function_arn,
            expected_vpc_id=expected_vpc_id,
            expected_subnet_ids=expected_subnet_ids,
            expected_security_group_ids=expected_security_group_ids,
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=tuple(SSM_PARAMETER_NAMES))
    arguments = parser.parse_args()

    try:
        validate_auth_lambda_contract(
            os.environ.get("EXPECTED_AWS_ACCOUNT_ID", ""),
            stage=arguments.stage,
        )
    except AuthLambdaPreflightError as error:
        print(f"::error::{error}", file=sys.stderr)
        return 1

    stages = (arguments.stage,) if arguments.stage else tuple(SSM_PARAMETER_NAMES)
    stage_label = " and ".join(current_stage.upper() for current_stage in stages)
    lambda_label = "Lambda" if len(stages) == 1 else "Lambdas"
    verb = "matches" if len(stages) == 1 else "match"
    print(f"Persistent {stage_label} customer-auth {lambda_label} {verb} the approved private network contract.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
