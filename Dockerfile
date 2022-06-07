# FROM alpine AS install -> does not work that nicely
FROM debian:bullseye AS install

RUN apt-get -y update && apt-get -y upgrade && \
    apt-get install -y --no-install-recommends \
    apt-transport-https \
    apt-utils \
    dwarves \
    locales \
    gnupg \
    python3 \
    python3-pip \
    python3-setuptools \
    python3-wheel

RUN pip3 install \
    argparse \
    jsonschema \
    coloredlogs

ENV RUBYOPT "-KU -E utf-8:utf-8"
ENV LANG='en_US.UTF-8' LANGUAGE='en_US:en' LC_ALL='en_US.UTF-8'
ENV PYTHONIOENCODING='utf-8'

RUN echo "alias ll='ls -laGFh'" >> /root/.bashrc
RUN echo 'en_US.UTF-8 UTF-8' > /etc/locale.gen && /usr/sbin/locale-gen

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
FROM install AS install-tools

# optionally add LLVM for dwarfdump debugging
# llvm-dwarfdump path/to/object.o -o object.dump
RUN echo 'deb http://apt.llvm.org/bullseye/ llvm-toolchain-bullseye main\n' >> /etc/apt/sources.list && \
    echo 'deb-src http://apt.llvm.org/bullseye/ llvm-toolchain-bullseye main\n' >> /etc/apt/sources.list \
    && apt-key adv --keyserver keyserver.ubuntu.com --recv-keys 15CF4D18AF4F7421 \
    && apt-get -y update \
    && apt-get install -y --no-install-recommends --allow-unauthenticated clang-tidy clang-format llvm \
    && rm -rf /var/lib/apt/lists/*

COPY ./run_pahole.py /usr/opt/run_pahole.py

# # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
FROM install-tools AS latest

VOLUME ["/project"]
WORKDIR /project
