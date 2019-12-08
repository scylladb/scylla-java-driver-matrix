#!/usr/bin/env bash
set -e

HELP="
$(basename $0) - Collects all the dynamically linked (".so") libraries the scylla binary depends on
so it can be used later on by ccm or dtest.

Usage: $(basename $0) scylla-binary output-directory
"

if (( $# != 2 )); then
    echo "${HELP}"
    exit 1
fi
SCYLLA_BIN=$1
OUTPUT_DIR=$2

if [ ! -f "${SCYLLA_BIN}" ]; then
    echo "${SCYLLA_BIN} doesn't exists"
    echo "${HELP}"
    exit 1
fi

mkdir -p ${OUTPUT_DIR}
ldd ${SCYLLA_BIN} | sed 's/^.*\s\(.*\)\s(.*)/\1/' | xargs -i cp {} ${OUTPUT_DIR}
