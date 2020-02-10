#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")

source "${SCRIPT_DIR}/aws_utils.sh"
setup_aws
setup_dryrun

PACKAGE_TYPE=${PACKAGE_TYPE:-wheel}
PACKAGE_PATH=${PACKAGE_PATH:-/home/circleci/project/final_pkgs}
DESIRED_CUDA=${DESIRED_CUDA:-cpu}

PACKAGES_TO_UPLOAD=$(find "${PACKAGE_PATH}" -type f -print0)

for pkg in ${PACKAGES_TO_UPLOAD}; do
    echo "+ Uploading ${pkg} to ${AWS_S3_BUCKET}/${PACKAGE_TYPE}/${DESIRED_CUDA}/"
    (
        set -x
        ${AWS_S3} \
            ${AWS_DRY_RUN_FLAG} \
            cp \
            --acl public-read \
            "${pkg}" \
            "${AWS_S3_BUCKET}/${PACKAGE_TYPE}/${DESIRED_CUDA}/"
    )
done

# TODO: Write a script to update HTML indices for pip
# TODO: Write a script to update conda indices
