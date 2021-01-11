#!/bin/bash

# Fetches and install Spark and its dependencies. To be invoked by the Dockerfile

# echo commands to the terminal output
set -ex

# Install JDK
apt-get update -y && \
    apt-get install -y software-properties-common && \
    add-apt-repository ppa:openjdk-r/ppa && \
    apt-get update -y && \
    apt-get install -y --force-yes ca-certificates-java && \
    apt-get install -y --force-yes openjdk-8-jdk && \
    apt-get install -y wget && \
    update-java-alternatives -s java-1.8.0-openjdk-amd64 && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

mkdir -p /opt/spark
mkdir -p /opt/spark/work-dir
touch /opt/spark/RELEASE

# Fetch Spark Distribution
#wget https://archive.apache.org/dist/spark/spark-3.0.0/spark-3.0.0-bin-hadoop2.7.tgz -O spark-dist.tgz
wget https://mirrors.ocf.berkeley.edu/apache/spark/spark-3.0.1/spark-3.0.1-bin-hadoop2.7.tgz -O spark-dist.tgz
#echo '98f6b92e5c476d7abb93cc179c2616aa5dc897da25753bd197e20ef54a28d945  spark-dist.tgz' | sha256sum --check
mkdir -p spark-dist
tar -xvf spark-dist.tgz -C spark-dist --strip-components 1

#Copy over required files
cp -rf spark-dist/jars /opt/spark/jars
cp -rf spark-dist/examples /opt/spark/examples
cp -rf spark-dist/python /opt/spark/python
cp -rf spark-dist/bin /opt/spark/bin
cp -rf spark-dist/sbin /opt/spark/sbin
cp -rf spark-dist/data /opt/spark/data
# Entrypoint for Driver/Executor pods
cp spark-dist/kubernetes/dockerfiles/spark/entrypoint.sh /opt/entrypoint.sh
chmod +x /opt/entrypoint.sh

rm -rf spark-dist.tgz
rm -rf spark-dist

# Fetch Hadoop Distribution with AWS Support
#wget http://apache.mirrors.tds.net/hadoop/common/hadoop-2.7.7/hadoop-2.7.7.tar.gz -O hadoop-dist.tgz
wget http://apache.mirrors.tds.net/hadoop/common/hadoop-2.10.1/hadoop-2.10.1.tar.gz -O hadoop-dist.tgz
#echo 'd129d08a2c9dafec32855a376cbd2ab90c6a42790898cabbac6be4d29f9c2026  hadoop-dist.tgz' | sha256sum --check
mkdir -p hadoop-dist
tar -xvf hadoop-dist.tgz -C hadoop-dist --strip-components 1

cp -rf hadoop-dist/share/hadoop/tools/lib/hadoop-aws-2.10.1.jar /opt/spark/jars
cp -rf hadoop-dist/share/hadoop/tools/lib/aws-java-sdk-bundle-1.11.271.jar /opt/spark/jars

rm -rf hadoop-dist.tgz
rm -rf hadoop-dist
