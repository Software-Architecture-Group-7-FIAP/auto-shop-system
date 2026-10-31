import json
import os
import subprocess
import unittest
from unittest.mock import patch

from scripts import mirror_ghcr_image_to_ecr


GITHUB_SHA = "0123456789abcdef0123456789abcdef01234567"
SOURCE_IMAGE = (
    "ghcr.io/software-architecture-group-7-fiap/auto-shop-system:sha-0123456"
)
TARGET_IMAGE = (
    "035611741563.dkr.ecr.us-east-1.amazonaws.com/auto-shop-system:sha-0123456"
)


class MirrorGhcrImageToEcrTests(unittest.TestCase):
    def setUp(self) -> None:
        self.environment = patch.dict(
            os.environ,
            {
                "AWS_REGION": "us-east-1",
                "GITHUB_ACTOR": "GustavoAcacioDev",
                "GITHUB_REPOSITORY": "Software-Architecture-Group-7-FIAP/auto-shop-system",
                "GITHUB_SHA": GITHUB_SHA,
                "GITHUB_TOKEN": "test-github-token",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.commands: list[tuple[list[str], str | None]] = []
        self.existing_ecr_config_id: str | None = None
        self.source_config_id = "sha256:source-config"

    def run_mock(self, command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        input_text = kwargs.get("input")
        self.commands.append((command, input_text if isinstance(input_text, str) else None))

        if command[:2] == ["docker", "login"]:
            return subprocess.CompletedProcess(command, 0, "Login Succeeded\n", "")

        if command[:2] == ["docker", "pull"]:
            return subprocess.CompletedProcess(command, 0, "Pulled\n", "")

        if command[:3] == ["docker", "image", "inspect"]:
            format_value = command[4]
            image_reference = command[5]
            if format_value == "{{.Id}}":
                config_id = (
                    self.source_config_id
                    if image_reference == SOURCE_IMAGE
                    else self.existing_ecr_config_id
                )
                if config_id is None:
                    return subprocess.CompletedProcess(command, 1, "", "image missing")
                return subprocess.CompletedProcess(command, 0, f"{config_id}\n", "")

            revision = GITHUB_SHA
            return subprocess.CompletedProcess(command, 0, f"{revision}\n", "")

        if command[:2] == ["aws", "sts"]:
            return subprocess.CompletedProcess(command, 0, "035611741563\n", "")

        if command[1:3] == ["ecr", "describe-repositories"]:
            repository = {
                "registryId": "035611741563",
                "repositoryName": "auto-shop-system",
                "repositoryUri": "035611741563.dkr.ecr.us-east-1.amazonaws.com/auto-shop-system",
                "imageTagMutability": "IMMUTABLE",
            }
            return subprocess.CompletedProcess(
                command, 0, json.dumps({"repositories": [repository]}), ""
            )

        if command[1:3] == ["ecr", "get-login-password"]:
            return subprocess.CompletedProcess(command, 0, "test-ecr-password\n", "")

        if command[1:3] == ["ecr", "batch-get-image"]:
            if self.existing_ecr_config_id is None:
                response = {
                    "images": [],
                    "failures": [
                        {"failureCode": "ImageNotFound", "failureReason": "Not found"}
                    ],
                }
            else:
                response = {
                    "images": [
                        {
                            "imageId": {
                                "imageTag": "sha-0123456",
                                "imageDigest": "sha256:manifest",
                            }
                        }
                    ],
                    "failures": [],
                }
            return subprocess.CompletedProcess(command, 0, json.dumps(response), "")

        if command[:2] == ["docker", "push"]:
            self.existing_ecr_config_id = self.source_config_id
            return subprocess.CompletedProcess(command, 0, "Pushed\n", "")

        if command[:2] == ["docker", "tag"]:
            return subprocess.CompletedProcess(command, 0, "Pushed\n", "")

        raise AssertionError(f"Unexpected command: {command}")

    def test_mirrors_verified_immutable_image_to_ecr(self) -> None:
        with patch.object(
            mirror_ghcr_image_to_ecr.subprocess, "run", side_effect=self.run_mock
        ):
            result = mirror_ghcr_image_to_ecr.mirror_image(SOURCE_IMAGE)

        self.assertEqual(result, TARGET_IMAGE)
        self.assertTrue(any(command[:2] == ["docker", "tag"] for command, _ in self.commands))
        self.assertTrue(any(command[:2] == ["docker", "push"] for command, _ in self.commands))
        ghcr_login = next(
            input_text
            for command, input_text in self.commands
            if command[:3] == ["docker", "login", "ghcr.io"]
        )
        self.assertEqual(ghcr_login, "test-github-token\n")
        command_arguments = " ".join(
            argument for arguments, _ in self.commands for argument in arguments
        )
        self.assertNotIn("test-github-token", command_arguments)

    def test_reuses_matching_immutable_ecr_tag_without_pushing(self) -> None:
        self.existing_ecr_config_id = self.source_config_id

        with patch.object(
            mirror_ghcr_image_to_ecr.subprocess, "run", side_effect=self.run_mock
        ):
            result = mirror_ghcr_image_to_ecr.mirror_image(SOURCE_IMAGE)

        self.assertEqual(result, TARGET_IMAGE)
        self.assertFalse(any(command[:2] == ["docker", "push"] for command, _ in self.commands))

    def test_rejects_existing_immutable_tag_for_a_different_image(self) -> None:
        self.existing_ecr_config_id = "sha256:other-config"

        with patch.object(
            mirror_ghcr_image_to_ecr.subprocess, "run", side_effect=self.run_mock
        ):
            with self.assertRaisesRegex(
                mirror_ghcr_image_to_ecr.MirrorError, "does not match"
            ):
                mirror_ghcr_image_to_ecr.mirror_image(SOURCE_IMAGE)

    def test_rejects_unexpected_ghcr_repository_or_mutable_tag(self) -> None:
        with patch.object(
            mirror_ghcr_image_to_ecr.subprocess, "run", side_effect=self.run_mock
        ) as run:
            with self.assertRaises(mirror_ghcr_image_to_ecr.MirrorError):
                mirror_ghcr_image_to_ecr.mirror_image(
                    "ghcr.io/other/repository:latest"
                )

        run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
