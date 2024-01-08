FROM python:3.11-slim-buster

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
    && gpg --homedir /tmp --no-default-keyring --keyring  /etc/apt/keyrings/xenial-security.gpg --keyserver keyserver.ubuntu.com --recv-keys 40976EAF437D05B5 3B4FE6ACC0B21F32 \
    && echo \
       "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/xenial-security.gpg] http://security.ubuntu.com/ubuntu \
       xenial-security main" | tee /etc/apt/sources.list.d/xenial-security.list > /dev/null \
    && apt-get -y update \
    && apt-get install -y  temurin-8-jdk maven git docker-ce-cli python2 libssl1.0.0 libapr1 \
    && apt-get install -y  temurin-11-jdk  \    
    && rm -rf /var/lib/apt/lists/*

RUN echo 2 | update-alternatives --config java

ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt

