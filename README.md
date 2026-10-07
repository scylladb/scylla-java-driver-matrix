# scylla-java-driver-matrix

Helper script to run integration test from multiple java-drivers against scylla

## Pre-release integration gate

The reusable workflow `.github/workflows/release-integration-tests.yml` runs the
Scylla Java driver against the same four Scylla targets used by this repository's
PR CI: `LATEST`, `PRIOR`, `LTS-LATEST`, and `LTS-PRIOR`. The caller supplies a
driver commit SHA and the version whose patches and ignore list should be used.
This allows testing a release candidate before its tag exists. All four lanes
must pass for the calling job to pass.

In the driver's release workflow, add a job before the release job:

```yaml
jobs:
  pre-release-integration:
    uses: scylladb/scylla-java-driver-matrix/.github/workflows/release-integration-tests.yml@<matrix-commit-sha>
    with:
      driver_ref: ${{ github.sha }}
      driver_version: 4.19.2.3
      matrix_ref: <matrix-commit-sha>

  release:
    needs: pre-release-integration
    # Existing release job configuration follows.
```

Pin `matrix_ref` to the same commit used in `uses`, so the checked-out runner,
patches, and workflow match. For a re-release, pass the predecessor commit of
the target tag as `driver_ref`, matching the driver's release checkout.


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

### Running from PyCharm:
- Create a basic Python configure.
- Working directory value is: `/home/oren/Desktop/github/python-driver-matrix`
- Script path value is: `main.py`
- Parameters value are:
  ```bash
  /home/oren/Desktop/github/java-driver/
  /home/oren/Desktop/github/scylla/
  --version
  4.x
  --scylla-version
  unstable/master/2022-01-03T13_22_36Z
  # To run a specific test needs to use
  # --tests
  # DirectCompressionIT
  ```
* To run a specific test needs to use

## Uploading docker images
   
when doing changes to requirements.txt, or any other change to docker image, it can be uploaded like this:

```bash
export UNIT_TEST_DOCKER_IMAGE=scylladb/scylla-cassandra-unit-tests:python3.11-$(date +'%Y%m%d')
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
