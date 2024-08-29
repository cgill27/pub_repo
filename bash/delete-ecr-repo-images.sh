#!/bin/bash

if [ -z "${1}" ]; then echo "Missing ecr repo argument! Exiting" && exit 2; fi

REGION="us-east-1"
PROFILE_NAME="development"
REPO="${1}"

aws --profile ${PROFILE_NAME} ecr batch-delete-image --region ${REGION} \
    --repository-name ${REPO} \
    --image-ids "$(aws --profile ${PROFILE_NAME} ecr list-images --region ${REGION} --repository-name ${REPO} --query 'imageIds[*]' --output json
)" || true

exit
