#!/usr/bin/env bash

set -e

VERSION=0.0.1
PREFIX=cortex
ANALYZER_PATH=analyzers
[[ -n ${PREFIX} ]] && PREFIX="${PREFIX}/"
ANALYZERS=${*:-${ANALYZER_PATH}/*}

for ANALYZER in ${ANALYZERS}
do
    ANALYZER_NAME=$(basename ${ANALYZER})
    mkdir -p docker/${ANALYZER_NAME}
    cp -r ${ANALYZER} docker/${ANALYZER_NAME}
    if grep -q '^cortexutils$' ${ANALYZER}/requirements.txt; then
        sed -e 's#^cortexutils$#git+https://github.com/TheHive-Project/cortexutils.git@feature/docker#' ${ANALYZER}/requirements.txt > docker/${ANALYZER_NAME}/${ANALYZER_NAME}/requirements.txt
    fi

    for FLAVOR in ${ANALYZER}/*.json
    do
        FLAVOR_NAME=$(cat ${FLAVOR} | jq -r .name)
        DOCKER_NAME=$(tr '[:upper:]' '[:lower:]' <<< ${FLAVOR_NAME})
        cat ${FLAVOR} | jq '. + {"image":"'${PREFIX}${DOCKER_NAME}:${VERSION}'"}' > docker/${ANALYZER_NAME}/$(basename ${FLAVOR})
        COMMAND=$(cat ${FLAVOR} | jq -r .command)
        DOCKER_FILE=docker/${ANALYZER_NAME}/Dockerfile-${FLAVOR_NAME}
        cat > ${DOCKER_FILE} <<- _EOF_
FROM python:3

ARG BUILD_DATE
ARG VCS_REF
ARG VERSION

WORKDIR /analyzer
COPY ${ANALYZER_NAME} ${ANALYZER_NAME}
RUN cat ${ANALYZER_NAME}/requirements.txt
RUN pip install --no-cache-dir -r ${ANALYZER_NAME}/requirements.txt
CMD ${COMMAND}
_EOF_
        docker build -t ${PREFIX}${DOCKER_NAME}:${VERSION} \
            --build-arg VERSION=${VERSION} \
            --build-arg BUILD_DATE=$(date -u +"%Y-%m-%dT%H:%M:%SZ") \
            --build-arg VCS_REF=$(git rev-parse --short HEAD) \
            -f ${DOCKER_FILE} docker/${ANALYZER_NAME}
    done
done