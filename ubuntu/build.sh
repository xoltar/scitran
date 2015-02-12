#!/bin/bash -e

# Prepare apt-get for usage
. /scitran/scripts/apt-get/bootstrap.sh
. /scitran/scripts/apt-get/update.sh

# Upgrades from ubuntu
apt-get dist-upgrade -y

# Cleanup
. /scitran/scripts/apt-get/clean.sh
