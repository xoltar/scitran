#!/bin/bash -e

# Custom repo for MongoDB
apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 7F0CEB10
echo 'deb http://downloads-distro.mongodb.org/repo/ubuntu-upstart dist 10gen' | tee /etc/apt/sources.list.d/10gen.list

# Prepare apt-get for usage
. /scitran/scripts/apt-get/update.sh

# Install
apt-get install -y mongodb-org

# Cleanup
. /scitran/scripts/apt-get/clean.sh
