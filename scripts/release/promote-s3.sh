#!/usr/bin/env bash

set -euo pipefail
SCRIPT_DIR=$(realpath "$(dirname "${BASH_SOURCE[0]}")")

source "${SCRIPT_DIR}/aws_utils.sh"
setup_aws
setup_dryrun

for package_type in whl conda libtorch; do
    echo "+ Syncing '${AWS_S3_BUCKET}/${package_type}' -> '${AWS_S3_STABLE_BUCKET}/${package_type}'"
    (
        set -x
        ${AWS_S3} \
            ${AWS_DRY_RUN_FLAG} \
            sync \
            --acl public-read \
            "${AWS_S3_BUCKET}/${package_type}" \
            "${AWS_S3_STABLE_BUCKET}/${package_type}"
    )
done

# TODO: Write a script to update HTML indices
