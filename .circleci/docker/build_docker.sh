#!/bin/bash

set -ex

retry () {
    $*  || (sleep 1 && $*) || (sleep 2 && $*)
}

ecr_login() {
  aws ecr get-authorization-token --region us-east-1 --output text --query 'authorizationData[].authorizationToken' |
    base64 -d |
    cut -d: -f2 |
    docker login -u AWS --password-stdin "$1"
}

ghcr_login() {
  # set +x here since we're echo'ing a cred
  (
    set +x
    echo "${GHCR_PAT}" | docker login ghcr.io -u pytorch --password-stdin
  )
}

# If UPSTREAM_BUILD_ID is set (see trigger job), then we can
# use it to tag this build with the same ID used to tag all other
# base image builds. Also, we can try and pull the previous
# image first, to avoid rebuilding layers that haven't changed.

#until we find a way to reliably reuse previous build, this last_tag is not in use
# last_tag="$(( CIRCLE_BUILD_NUM - 1 ))"
tag="${DOCKER_TAG}"
cache_to_tag="$(git rev-parse HEAD)"
# TODO: Add a way to calculate a cache_from_tag

registry="308535385114.dkr.ecr.us-east-1.amazonaws.com"
cache_registry="ghcr.io"
image="${registry}/pytorch/${IMAGE_NAME}"
cache_image="${cache_registry}/pytorch/ci-image-cache:${IMAGE_NAME}"

# Retry on timeouts (can happen on job stampede).
retry ecr_login "${registry}"

# Logout on exit
trap "docker logout ${registry}" EXIT

# export EC2=1
# export JENKINS=1

if [[ -n ${PUBLISH_CACHE:-} ]]; then
  retry ghcr_login
  CACHE_TO_FLAG="--cache-to=type=registry,ref=${cache_image}-${cache_to_tag}"
fi

# Build new image
./build.sh ${IMAGE_NAME} -t "${image}:${tag}"

docker push "${image}:${tag}"

docker save -o "${IMAGE_NAME}:${tag}.tar" "${image}:${tag}"
aws s3 cp "${IMAGE_NAME}:${tag}.tar" "s3://ossci-linux-build/pytorch/base/${IMAGE_NAME}:${tag}.tar" --acl public-read
