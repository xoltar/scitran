#!/bin/bash -e

# Prepare apt-get for usage
. /scitran/scripts/apt-get/update.sh

# Install
apt-get dist-upgrade -y
apt-get install -y ca-certificates
update-ca-certificates

# Cleanup
. /scitran/scripts/apt-get/clean.sh
