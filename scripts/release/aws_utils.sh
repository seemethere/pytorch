#!/usr/bin/env bash

setup_aws() {
    # Sets up a bunch of useful AWS environment variables

    export AWS=${AWS:-aws}
    # Specify an S3 bucket that's delimited by git sha for promotion later
    export AWS_S3_BUCKET=${AWS_S3_BUCKET:-s3://pytorch-release/$(git rev-parse HEAD)}
    export AWS_S3_STABLE_BUCKET=${AWS_S3_STABLE_BUCKET:-s3://pytorch/}
    export AWS_S3="aws s3 --no-progress --only-show-errors"
}

setup_dryrun() {
    # We don't want to actually upload things on a non-dry run
    if ! git describe --tags --exact >/dev/null 2>/dev/null; then
        echo "- WARNING: Script run on non-tag, doing dry run instead"
        DRY_RUN="true"
    fi
    # Maybe we can swap this out for a docker container at a later time
    export DRY_RUN=${DRY_RUN:-true}
    export AWS_DRY_RUN_FLAG=${DRY_RUN:---dryrun}
    if [[ "${DRY_RUN}" != "false" ]]; then
        export AWS_DRY_RUN_FLAG=""
    fi
}

download_bucket_to_local() {
    DIR=${DIR:-.}
    SUB_PATH=${SUB_PATH:-}
    BUCKET=${BUCKET:-${AWS_S3_BUCKET}}
    setup_aws
    ${AWS_S3} sync "${BUCKET}/${SUB_PATH}" "${DIR}"
}
