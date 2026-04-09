FROM python:3.11-slim-bookworm

RUN apt-get -y update \
    && apt-get install -y wget apt-transport-https \
    && apt-get -y install \
                    ca-certificates \
                    curl \
                    gnupg \
                    lsb-release \
    && mkdir -p /etc/apt/keyrings \
    && curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg \
    && echo \
       "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
       $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null \
    && wget -O - https://packages.adoptium.net/artifactory/api/gpg/key/public | tee /etc/apt/keyrings/adoptium.asc \
    && echo "deb [signed-by=/etc/apt/keyrings/adoptium.asc] https://packages.adoptium.net/artifactory/deb $(awk -F= '/^VERSION_CODENAME/{print$2}' /etc/os-release) main" | tee /etc/apt/sources.list.d/adoptium.list \
    && apt-get -y update \
    && apt-get install -y  temurin-8-jdk git docker-ce-cli libapr1 \
    && apt-get install -y  temurin-11-jdk  \
    && arch="$(dpkg --print-architecture)" \
    && wget "https://snapshot.debian.org/archive/debian/20231003T205808Z/pool/main/o/openssl/libssl1.1_1.1.1w-0+deb11u1_${arch}.deb" \
    && apt-get install -y "./libssl1.1_1.1.1w-0+deb11u1_${arch}.deb" \
    && rm -f "./libssl1.1_1.1.1w-0+deb11u1_${arch}.deb" \
    && rm -rf /var/lib/apt/lists/*  \
    && wget https://archive.apache.org/dist/maven/maven-3/3.9.14/binaries/apache-maven-3.9.14-bin.tar.gz  \
    && tar -xvzf apache-maven-3.9.14-bin.tar.gz -C /opt \
    && rm -f apache-maven-3.9.14-bin.tar.gz \
    && ln -s /opt/apache-maven-3.9.14 /opt/maven

ENV MAVEN_HOME=/opt/maven
ENV PATH="$MAVEN_HOME/bin:${PATH}"

RUN echo 2 | update-alternatives --config java

ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt
RUN pip install ruamel.yaml
