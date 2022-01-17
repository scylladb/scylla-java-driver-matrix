FROM python:3.8-slim-buster

RUN apt-get -y update \
    # To install "java version 1.8" it is necessary to install the following dependence
    && apt-get install -y software-properties-common \
    && apt-add-repository 'deb http://security.debian.org/debian-security stretch/updates main' \
    && apt-get -y update \
    && apt-get install -y openjdk-8-jdk \
    && apt-get install -y maven git \
    && rm -rf /var/lib/apt/lists/*

ADD requirements.txt requirements.txt
RUN pip install -r requirements.txt

