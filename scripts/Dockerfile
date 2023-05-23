FROM python:3.11-slim-buster

RUN apt-get -y update \
    && apt-get install -y wget apt-transport-https \
    && mkdir -p /etc/apt/keyrings \
    && wget -O - https://packages.adoptium.net/artifactory/api/gpg/key/public | tee /etc/apt/keyrings/adoptium.asc \
    && echo "deb [signed-by=/etc/apt/keyrings/adoptium.asc] https://packages.adoptium.net/artifactory/deb $(awk -F= '/^VERSION_CODENAME/{print$2}' /etc/os-release) main" | tee /etc/apt/sources.list.d/adoptium.list \
    && apt-get -y update \
    && apt-get install -y  temurin-8-jdk maven git \
    && apt-get install -y  temurin-11-jdk  \    
    && rm -rf /var/lib/apt/lists/*

RUN echo 2 | update-alternatives --config java

ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt

