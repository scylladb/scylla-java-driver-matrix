#!/usr/bin/env bash
set -e

help_text="
$(basename $0) - Run java-driver integration tests over scylla using docker


    Optional values can be set via environment variables

    Running dtest from scylla source code :
        CASSANDRA_DIR
            directory of the scylla source code or specific build output variant
            '../scylla/build/release' or '../scylla/build/debug' default to '../scylla'
        SCYLLA_DBUILD_SO_DIR
            directory of dynamic .so files to be collected. defaults to '\$CASSANDRA_DIR/dynamic_libs'
        TOOLS_JAVA_DIR
            directory of scylla java tools, should be already compiled. defaults to '../scylla-tools-java'
        JMX_DIR
            directory of scylla jmx, should be already compiled. defaults to '../scylla-jmx'

    Running from scylla relocatable packages:

        SCYLLA_VERSION
            a version from scylla downloads: http://downloads.scylladb.com/relocatable/unstable/master/
            for example: 'unstable/master:380'
        SCYLLA_CORE_PACKAGE
            local path or url for taking the relocatable core package
        SCYLLA_JAVA_TOOLS_PACKAGE
            local path or url for taking the relocatable java tools package
        SCYLLA_JMX_PACKAGE
            local path or url for taking the relocatable jmx package

    Other options:
        CCM_DIR
            directory of scylla ccm, should be already compiled. defaults to '../scylla-ccm'


    ./run_test.sh mvn test
"

here="$(realpath $(dirname "$0"))"
DOCKER_IMAGE="$(<"$here/image")"

export SCYLLA_JAVA_DRIVER_MATRIX_DIR=${SCYLLA_JAVA_DRIVER_MATRIX_DIR:-`pwd`}
export CASSANDRA_DIR=${CASSANDRA_DIR:-`pwd`/../scylla}
SCYLLA_ROOT_DIR=$(echo $CASSANDRA_DIR | sed 's|/build/.*||')

# if CASSANDRA_DIR didn't point to specific variant default to release
if [[ ${CASSANDRA_DIR} == ${SCYLLA_ROOT_DIR} ]]; then
    export CASSANDRA_DIR=${CASSANDRA_DIR}/build/release
fi
export TOOLS_JAVA_DIR=${TOOLS_JAVA_DIR:-`pwd`/../scylla-tools-java}
export JMX_DIR=${JMX_DIR:-`pwd`/../scylla-jmx}
export CCM_DIR=${CCM_DIR:-`pwd`/../scylla-ccm}
export SCYLLA_DBUILD_SO_DIR=${SCYLLA_DBUILD_SO_DIR:-${CASSANDRA_DIR}/dynamic_libs}

mkdir -p ${HOME}/.ccm
mkdir -p ${HOME}/.m2
mkdir -p ${HOME}/.local/lib
mkdir -p ${HOME}/.config

function check_directory_exists()
{
    if [[ ! -d ${!1} ]]; then
        echo -e "\e[31m\$$1 = ${!1} directory not found\e[0m"
        echo "${help_text}"
        exit 1
    fi
}

check_directory_exists SCYLLA_JAVA_DRIVER_MATRIX_DIR
check_directory_exists CCM_DIR

# export all BUILD_* env vars into the docker run
BUILD_OPTIONS=$(env | sed -n 's/^\(BUILD_[^=]\+\)=.*/--env \1/p')
# export all JOB_* env vars into the docker run
JOB_OPTIONS=$(env | sed -n 's/^\(JOB_[^=]\+\)=.*/--env \1/p')
# export all AWS_* env vars into the docker run
AWS_OPTIONS=$(env | sed -n 's/^\(AWS_[^=]\+\)=.*/--env \1/p')

DOCKER_CONFIG_MNT="-v $(eval echo ~${USER})/.docker:${HOME}/.docker"

if [[ -z ${SCYLLA_VERSION} ]]; then
    # Use locally built scylla from source

    check_directory_exists CASSANDRA_DIR
    check_directory_exists TOOLS_JAVA_DIR
    check_directory_exists JMX_DIR

    if [[ ! -d ${SCYLLA_DBUILD_SO_DIR} ]]; then
        echo "scylla was built with dbuild, and SCYLLA_DBUILD_SO_DIR wasn't supplied or exists"
        set +e
        ${SCYLLA_ROOT_DIR}/tools/toolchain/dbuild -v ${CASSANDRA_DIR}:${CASSANDRA_DIR} -v ${SCYLLA_JAVA_DRIVER_MATRIX_DIR}/scripts/dbuild_collect_so.sh:/bin/dbuild_collect_so.sh -- dbuild_collect_so.sh  ${CASSANDRA_DIR}/scylla ${SCYLLA_DBUILD_SO_DIR}
        set -e
    fi

    DOCKER_COMMAND_PARAMS="
    -v ${SCYLLA_ROOT_DIR}:${SCYLLA_ROOT_DIR} \
    -v ${TOOLS_JAVA_DIR}:${TOOLS_JAVA_DIR} \
    -v ${JMX_DIR}:${JMX_DIR} \
    -e SCYLLA_DBUILD_SO_DIR \
    -e CASSANDRA_DIR
    "
else
    # Use locally built scylla with relocatable package

    # export all SCYLLA_* env vars into the docker run
    SCYLLA_OPTIONS=$(env | sed -n 's/^\(SCYLLA_[^=]\+\)=.*/--env \1/p')

    DOCKER_COMMAND_PARAMS="${SCYLLA_OPTIONS}"
fi

# if in jenkins also mount the workspace into docker
if [[ -d ${WORKSPACE} ]]; then
WORKSPACE_MNT="-v ${WORKSPACE}:${WORKSPACE}"
else
WORKSPACE_MNT=""
fi

group_args=()
for gid in $(id -G); do
    group_args+=(--group-add "$gid")
done


docker_cmd="docker run --detach=true \
    ${WORKSPACE_MNT} \
    ${DOCKER_COMMAND_PARAMS} \
    ${DOCKER_CONFIG_MNT} \
    -v ${CCM_DIR}:${CCM_DIR} \
    -v ${SCYLLA_JAVA_DRIVER_MATRIX_DIR}:${SCYLLA_JAVA_DRIVER_MATRIX_DIR} \
    -e HOME \
    -e SCYLLA_EXT_OPTS \
    -e NODE_TOTAL \
    -e NODE_INDEX \
    -e WORKSPACE \
    ${BUILD_OPTIONS} \
    ${JOB_OPTIONS} \
    ${AWS_OPTIONS} \
    -w ${SCYLLA_JAVA_DRIVER_MATRIX_DIR} \
    -v /var/run/docker.sock:/var/run/docker.sock \
    -v /sys/fs/cgroup:/sys/fs/cgroup:ro \
    -v /etc/passwd:/etc/passwd:ro \
    -v /etc/group:/etc/group:ro \
    -u $(id -u ${USER}):$(id -g ${USER}) \
    ${group_args[@]} \
    --tmpfs ${HOME}/.cache \
    -v ${HOME}/.local:${HOME}/.local \
    -v ${HOME}/.ccm:${HOME}/.ccm \
    -v ${HOME}/.m2:${HOME}/.m2 \
    -v ${HOME}/.config:${HOME}/.config \
    --network=bridge --privileged \
    ${DOCKER_IMAGE} bash -c 'pip install --user -e ${CCM_DIR} ;  export PATH=\$PATH:\${HOME}/.local/bin; $*'"

echo "Running Docker: $docker_cmd"
container=$(eval $docker_cmd)


kill_it() {
    if [[ -n "$container" ]]; then
        docker rm -f "$container" > /dev/null
        container=
    fi
}

trap kill_it SIGTERM SIGINT SIGHUP EXIT

docker logs "$container" -f

if [[ -n "$container" ]]; then
    exitcode="$(docker wait "$container")"
else
    exitcode=99
fi

echo "Docker exitcode: $exitcode"

kill_it

trap - SIGTERM SIGINT SIGHUP EXIT

# after "docker kill", docker wait will not print anything
[[ -z "$exitcode" ]] && exitcode=1

exit "$exitcode"

