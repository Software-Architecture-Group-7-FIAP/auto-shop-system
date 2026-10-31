#!/usr/bin/env python3
"""Mirror the authorized GHCR release image into the private staging ECR repository."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from typing import Any


ECR_REPOSITORY = "auto-shop-system"
IMAGE_TAG_PATTERN = re.compile(r"^sha-[0-9a-f]{7}$")
GITHUB_SHA_PATTERN = re.compile(r"^[0-9a-f]{40}$")
ACCOUNT_ID_PATTERN = re.compile(r"^[0-9]{12}$")


class MirrorError(RuntimeError):
    """Raised when an image cannot be safely mirrored to ECR."""


def _required_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MirrorError(f"Required environment value {name} is missing.")
    return value


def _run(command: list[str], *, stdin: str | None = None) -> str:
    try:
        result = subprocess.run(
            command,
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as error:
        raise MirrorError("A required Docker or AWS CLI command could not be started.") from error

    if result.returncode != 0:
        # CLI diagnostics can contain registry or environment details. Keep workflow logs generic.
        raise MirrorError("A required Docker or AWS CLI command failed.")
    return result.stdout.strip()


def _inspect_image(image_reference: str, format_value: str) -> str:
    return _run(
        ["docker", "image", "inspect", "--format", format_value, image_reference]
    )


def _image_revision(image_reference: str) -> str:
    return _inspect_image(
        image_reference,
        '{{index .Config.Labels "org.opencontainers.image.revision"}}',
    )


def _ecr_image_present(repository: str, region: str, tag: str) -> bool:
    response_text = _run(
        [
            "aws",
            "ecr",
            "batch-get-image",
            "--repository-name",
            repository,
            "--image-ids",
            f"imageTag={tag}",
            "--region",
            region,
            "--output",
            "json",
            "--no-cli-pager",
        ]
    )
    try:
        response: dict[str, Any] = json.loads(response_text)
        images = response.get("images", [])
        failures = response.get("failures", [])
    except (TypeError, json.JSONDecodeError) as error:
        raise MirrorError("ECR returned an invalid image lookup response.") from error

    if isinstance(images, list) and images:
        if len(images) != 1 or not isinstance(images[0], dict):
            raise MirrorError("ECR returned an ambiguous image lookup response.")
        return True

    if (
        isinstance(failures, list)
        and len(failures) == 1
        and isinstance(failures[0], dict)
        and failures[0].get("failureCode") == "ImageNotFound"
    ):
        return False

    raise MirrorError("ECR could not confirm whether the immutable image tag exists.")


def _ecr_repository_uri(account_id: str, region: str) -> str:
    response_text = _run(
        [
            "aws",
            "ecr",
            "describe-repositories",
            "--repository-names",
            ECR_REPOSITORY,
            "--region",
            region,
            "--output",
            "json",
            "--no-cli-pager",
        ]
    )
    try:
        response: dict[str, Any] = json.loads(response_text)
        repositories = response.get("repositories", [])
    except (TypeError, json.JSONDecodeError) as error:
        raise MirrorError("ECR returned an invalid repository response.") from error

    if not isinstance(repositories, list) or len(repositories) != 1:
        raise MirrorError("The expected ECR repository was not found uniquely.")
    repository = repositories[0]
    if not isinstance(repository, dict):
        raise MirrorError("ECR returned an invalid repository entry.")

    expected_uri = (
        f"{account_id}.dkr.ecr.{region}.amazonaws.com/{ECR_REPOSITORY}"
    )
    if (
        repository.get("registryId") != account_id
        or repository.get("repositoryName") != ECR_REPOSITORY
        or repository.get("repositoryUri") != expected_uri
        or repository.get("imageTagMutability") != "IMMUTABLE"
    ):
        raise MirrorError("The ECR repository does not match the immutable expected registry.")
    return expected_uri


def mirror_image(source_image: str) -> str:
    github_repository = _required_environment("GITHUB_REPOSITORY").lower()
    github_sha = _required_environment("GITHUB_SHA").lower()
    github_actor = _required_environment("GITHUB_ACTOR")
    github_token = _required_environment("GITHUB_TOKEN")
    aws_region = _required_environment("AWS_REGION")

    if not GITHUB_SHA_PATTERN.fullmatch(github_sha):
        raise MirrorError("GITHUB_SHA must be a 40-character lowercase commit SHA.")
    if not re.fullmatch(r"[a-z0-9-]+", aws_region):
        raise MirrorError("AWS_REGION contains unsupported characters.")

    expected_tag = f"sha-{github_sha[:7]}"
    expected_source = f"ghcr.io/{github_repository}:{expected_tag}"
    if not IMAGE_TAG_PATTERN.fullmatch(expected_tag) or source_image != expected_source:
        raise MirrorError("The source image must be this repository's immutable commit tag.")

    _run(
        ["docker", "login", "ghcr.io", "--username", github_actor, "--password-stdin"],
        stdin=f"{github_token}\n",
    )
    _run(["docker", "pull", source_image])
    source_config_id = _inspect_image(source_image, "{{.Id}}")
    if _image_revision(source_image) != github_sha:
        raise MirrorError("The GHCR image revision label does not match the workflow commit.")

    account_id = _run(
        [
            "aws",
            "sts",
            "get-caller-identity",
            "--query",
            "Account",
            "--output",
            "text",
            "--no-cli-pager",
        ]
    )
    if not ACCOUNT_ID_PATTERN.fullmatch(account_id):
        raise MirrorError("AWS returned an invalid account ID.")

    repository_uri = _ecr_repository_uri(account_id, aws_region)
    target_image = f"{repository_uri}:{expected_tag}"
    ecr_password = _run(
        ["aws", "ecr", "get-login-password", "--region", aws_region, "--no-cli-pager"]
    )
    _run(
        [
            "docker",
            "login",
            f"{account_id}.dkr.ecr.{aws_region}.amazonaws.com",
            "--username",
            "AWS",
            "--password-stdin",
        ],
        stdin=f"{ecr_password}\n",
    )

    if _ecr_image_present(ECR_REPOSITORY, aws_region, expected_tag):
        _run(["docker", "pull", target_image])
        target_config_id = _inspect_image(target_image, "{{.Id}}")
        if (
            target_config_id != source_config_id
            or _image_revision(target_image) != github_sha
        ):
            raise MirrorError("The existing immutable ECR tag does not match this GHCR image.")
        return target_image

    _run(["docker", "tag", source_image, target_image])
    _run(["docker", "push", target_image])
    if not _ecr_image_present(ECR_REPOSITORY, aws_region, expected_tag):
        raise MirrorError("ECR did not confirm the image push.")
    _run(["docker", "pull", target_image])
    target_config_id = _inspect_image(target_image, "{{.Id}}")
    if target_config_id != source_config_id or _image_revision(target_image) != github_sha:
        raise MirrorError("The ECR image does not match the GHCR source after push.")
    return target_image


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: mirror_ghcr_image_to_ecr.py GHCR_IMAGE_REFERENCE", file=sys.stderr)
        return 2

    try:
        print(mirror_image(sys.argv[1]))
    except MirrorError as error:
        print(f"Image mirror failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
