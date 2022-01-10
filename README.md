# scylla-java-driver-matrix

Helper script to run integration test from multiple java-drivers against scylla


## Usage

### Running Locally

```bash
apt-get install openjdk-8-jdk-headless maven python-virtualenv

virtualenv .ccm-venv
source .ccm-venv/bin/activate 

pip install -r scripts/requirements.txt

python3 ./main.py ../java-driver/ --versions 4.3.0 --scylla-version unstable/master:201910020524
```

### Running with docker
```bash
./scripts/run_test.sh python ./main.py ../java-driver/ --version 4.3.0 --scylla-version unstable/master:201910020524```
```

### Running specific test
```bash
./scripts/run_test.sh python3 ./main.py ../java-driver/ --tests QueryTraceIT --version 4.1.0 --scylla-version u
nstable/master:201912142059
```

## Uploading docker images
   
when doing changes to requirements.txt, or any other change to docker image, it can be uploaded like this:

```bash
export UNIT_TEST_DOCKER_IMAGE=scylladb/scylla-cassandra-unit-tests:python3.8-$(date +'%Y%m%d')
docker build ./scripts/ -t ${UNIT_TEST_DOCKER_IMAGE}
docker push ${UNIT_TEST_DOCKER_IMAGE}
echo "${UNIT_TEST_DOCKER_IMAGE}" > scripts/image
```

**Note:** you'll need permissions on the scylladb dockerhub organization for uploading images

## TODOs
* fix `ccm node1 pause`, a bug in CCM

```
# running specific tests stright from java-driver dir (on branches 4.x)
mvn -pl infra-tests install
mvn -pl integration-tests -Dtest='SelectOtherClausesIT,ExecutionInfoWarningsIT' test -Dscylla.version=unstable/master:201910020524

# running on java-driver branches 3.x
mvn -pl driver-core test -Dtest.groups='long' -Dtest='*' -Dscylla.version=unstable/master:201910020524

```