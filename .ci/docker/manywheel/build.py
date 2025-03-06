#!/usr/bin/env python3
# Script used only in CD pipeline

import argparse
from dataclasses import dataclass
import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def run_cmd(
    cmd: list[str], check: bool = True, environ: Optional[dict] = None
) -> subprocess.CompletedProcess:
    """Run a command with proper logging."""
    logger.debug("Running command: %s", " ".join(cmd))
    cmd_environ = {**os.environ}
    if environ:
        cmd_environ.update(environ)
    return subprocess.run(
        cmd,
        env=cmd_environ,
        check=check,
        text=True,
    )


def get_git_info() -> tuple[str, str]:
    """Get git branch name and commit SHA."""
    github_ref = os.environ.get("GITHUB_REF")
    github_sha = os.environ.get("GITHUB_SHA")

    if github_ref:
        branch_name = github_ref.split("/")[-1]
    else:
        try:
            branch_name = subprocess.check_output(
                ["git", "symbolic-ref", "-q", "HEAD"], text=True
            ).strip()
        except subprocess.CalledProcessError:
            try:
                branch_name = subprocess.check_output(
                    ["git", "describe", "--tags", "--exact-match"], text=True
                ).strip()
            except subprocess.CalledProcessError:
                branch_name = ""

        branch_name = branch_name.split("/")[-1] if branch_name else ""

    if not github_sha:
        github_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip()

    return branch_name, github_sha


@dataclass
class Config:
    """Configuration for building Docker images."""

    target: str
    gpu_arch_type: str
    gpu_arch_version: str
    docker_tag: str
    gpu_image: str
    many_linux_version: str
    dockerfile_suffix: str = ""


@dataclass
class CudaConfig(Config):
    """Configuration for building CUDA Docker images"""

    @property
    def docker_gpu_build_arg(self) -> str:
        """Build args for CUDA configuration"""
        return f"--build-arg BASE_CUDA_VERSION={self.gpu_arch_version}"


@dataclass
class RocmConfig(Config):
    """Configuration for building ROCm Docker images"""

    pytorch_rocm_arch: str = (
        "gfx900;gfx906;gfx908;gfx90a;gfx942;gfx1030;gfx1100;gfx1101;gfx1102"
    )

    @property
    def docker_gpu_build_arg(self) -> str:
        """Build args for ROCm configuration"""
        return (
            f"--build-arg ROCM_VERSION={self.gpu_arch_version} "
            f"--build-arg PYTORCH_ROCM_ARCH='{self.pytorch_rocm_arch}' "
        )


def get_build_config(gpu_arch_type: str, gpu_arch_version: str) -> Config:
    """Get build configuration based on GPU architecture type."""
    if gpu_arch_type == "cpu":
        return Config(
            target="cpu_final",
            gpu_arch_type=gpu_arch_type,
            gpu_arch_version=gpu_arch_version,
            docker_tag="cpu",
            gpu_image="amd64/almalinux:8",
            many_linux_version="2_28",
        )
    elif gpu_arch_type == "cpu-aarch64":
        return Config(
            target="final",
            gpu_arch_type=gpu_arch_type,
            gpu_arch_version=gpu_arch_version,
            docker_tag="cpu-aarch64",
            gpu_image="arm64v8/almalinux:8",
            many_linux_version="2_28_aarch64",
        )
    elif gpu_arch_type == "cpu-s390x":
        return Config(
            target="final",
            gpu_arch_type=gpu_arch_type,
            gpu_arch_version=gpu_arch_version,
            docker_tag="cpu-s390x",
            gpu_image="s390x/almalinux:8",
            many_linux_version="s390x",
        )
    elif gpu_arch_type == "cuda":
        return CudaConfig(
            target="cuda_final",
            gpu_arch_type=gpu_arch_type,
            gpu_arch_version=gpu_arch_version,
            docker_tag=f"cuda{gpu_arch_version}",
            gpu_image="amd64/almalinux:8",
            many_linux_version="2_28",
        )
    elif gpu_arch_type == "cuda-aarch64":
        return CudaConfig(
            gpu_arch_type=gpu_arch_type,
            gpu_arch_version=gpu_arch_version,
            docker_tag=f"cuda{gpu_arch_version}",
            gpu_image="arm64v8/centos:7",
            many_linux_version="_cuda_aarch64",
            dockerfile_suffix="_cuda_aarch64",
        )
    elif gpu_arch_type == "rocm":
        return RocmConfig(
            gpu_arch_type=gpu_arch_type,
            gpu_arch_version=gpu_arch_version,
            docker_tag=f"rocm{gpu_arch_version}",
            gpu_image=f"rocm/dev-almalinux-8:{gpu_arch_version}-complete",
            many_linux_version="2_28",
        )
    elif gpu_arch_type == "xpu":
        return Config(
            target="xpu_final",
            gpu_arch_type=gpu_arch_type,
            gpu_arch_version=gpu_arch_version,
            docker_tag="xpu",
            gpu_image="amd64/almalinux:8",
            many_linux_version="2_28",
        )
    else:
        logger.error("Unrecognized GPU_ARCH_TYPE: %s", gpu_arch_type)
        sys.exit(1)


def patch_docker_service_for_ci() -> None:
    """Patch docker service for CI."""
    if os.environ.get("CI") and os.uname().machine != "s390x":
        logger.info("Patching docker service for CI")
        run_cmd(
            [
                "sudo",
                "sed",
                "-i",
                "s/LimitNOFILE=infinity/LimitNOFILE=1048576/",
                "/usr/lib/systemd/system/docker.service",
            ]
        )
        run_cmd(["sudo", "systemctl", "daemon-reload"])
        run_cmd(["sudo", "systemctl", "restart", "docker"])


def build_docker_image(
    docker_image: str,
    config: Config,
    topdir: Path,
    dry_run: bool = False,
) -> None:
    """Build docker image with appropriate configuration."""
    # Set the environment variable for Docker BuildKit
    os.environ["DOCKER_BUILDKIT"] = "1"

    dockerfile = (
        topdir
        / ".ci"
        / "docker"
        / "manywheel"
        / f"Dockerfile{config.dockerfile_suffix}"
    )
    docker_context = topdir / ".ci" / "docker"

    docker_build_command = [
        "docker",
        "build",
        *config.docker_gpu_build_arg.split(),
        "--build-arg",
        f"GPU_IMAGE={config.gpu_image}",
        "--target",
        config.target,
        "-t",
        docker_image,
        "-f",
        str(dockerfile),
        str(docker_context),
    ]

    # Filter out empty elements
    docker_build_command = [arg for arg in docker_build_command if arg]

    if dry_run:
        logger.info("DRY RUN: Docker build command: %s", " ".join(docker_build_command))
    else:
        logger.info(
            "Building Docker image with command: %s", " ".join(docker_build_command)
        )
        run_cmd(docker_build_command)


def push_docker_image(docker_image: str, branch_name: str, commit_sha: str) -> None:
    """Push Docker image to registry."""
    docker_image_branch_tag = f"{docker_image}-{branch_name}"
    docker_image_sha_tag = f"{docker_image}-{commit_sha}"

    logger.info("Pushing Docker image: %s", docker_image)
    run_cmd(["docker", "push", docker_image])

    if os.environ.get("GITHUB_REF"):
        logger.info("Tagging and pushing branch and SHA tags")
        run_cmd(["docker", "tag", docker_image, docker_image_branch_tag])
        run_cmd(["docker", "tag", docker_image, docker_image_sha_tag])
        run_cmd(["docker", "push", docker_image_branch_tag])
        run_cmd(["docker", "push", docker_image_sha_tag])


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build Docker images for manywheel packages"
    )
    parser.add_argument("image", type=str, help="Image name without 'pytorch/' prefix")
    parser.add_argument(
        "--gpu-arch-type",
        type=str,
        default="cpu",
        help="GPU architecture type (cpu, cuda, rocm, etc.)",
    )
    parser.add_argument(
        "--gpu-arch-version", type=str, default="", help="GPU architecture version"
    )
    parser.add_argument(
        "--many-linux-version", type=str, default="", help="Manylinux version to use"
    )
    parser.add_argument(
        "--dockerfile-suffix", type=str, default="", help="Suffix for the Dockerfile"
    )
    parser.add_argument(
        "--with-push",
        action="store_true",
        help="Push the built Docker image to registry",
    )
    parser.add_argument(
        "--docker-registry",
        type=str,
        default="docker.io",
        help="Docker registry to push to",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print the docker build command without executing it",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Set Docker image name
    docker_image = f"pytorch/{args.image}"

    # Use environment variables as defaults if not provided in arguments
    gpu_arch_type = os.environ.get("GPU_ARCH_TYPE", args.gpu_arch_type)
    gpu_arch_version = os.environ.get("GPU_ARCH_VERSION", args.gpu_arch_version)
    many_linux_version = os.environ.get("MANY_LINUX_VERSION", args.many_linux_version)
    dockerfile_suffix = os.environ.get("DOCKERFILE_SUFFIX", args.dockerfile_suffix)
    with_push = os.environ.get("WITH_PUSH") == "true" or args.with_push
    dry_run = args.dry_run

    # Get build configuration
    config = get_build_config(gpu_arch_type, gpu_arch_version)

    # Override config with command line arguments if provided
    if many_linux_version:
        config.many_linux_version = many_linux_version
    if dockerfile_suffix:
        config.dockerfile_suffix = dockerfile_suffix

    # If many_linux_version is set and dockerfile_suffix is not, set it
    if config.many_linux_version and not config.dockerfile_suffix:
        config.dockerfile_suffix = f"_{config.many_linux_version}"

    # Get top-level directory of git repository
    topdir = Path(
        subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True
        ).strip()
    )

    # Patch Docker service if in CI and not in dry-run mode
    if not dry_run:
        patch_docker_service_for_ci()

    # Build Docker image
    build_docker_image(docker_image, config, topdir, dry_run)

    # Push Docker image if requested and not in dry-run mode
    if with_push and not dry_run:
        branch_name, commit_sha = get_git_info()
        push_docker_image(docker_image, branch_name, commit_sha)
    elif with_push and dry_run:
        branch_name, commit_sha = get_git_info()
        logger.info(
            "DRY RUN: Would push Docker image %s and tags %s, %s",
            docker_image,
            f"{docker_image}-{branch_name}",
            f"{docker_image}-{commit_sha}",
        )


if __name__ == "__main__":
    main()
