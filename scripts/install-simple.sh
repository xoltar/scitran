#! /bin/bash -e

#
# Box setup
#

# Speed up installs and don't create cache files
#	See: https://github.com/dotcloud/docker/pull/1883#issuecomment-24434115
echo "force-unsafe-io"                 > /etc/dpkg/dpkg.cfg.d/02apt-speedup
echo "Acquire::http {No-Cache=True;};" > /etc/apt/apt.conf.d/no-cache
chmod 0644 /etc/dpkg/dpkg.cfg.d/02apt-speedup
chmod 0644 /etc/apt/apt.conf.d/no-cache

# Set to non-interactive installs
export DEBIAN_FRONTEND=noninteractive

# Aggressively nuke apt cache
apt-get autoremove -y
apt-get clean -y
rm -rf /var/lib/apt/lists

# Ubuntu essentials
apt-get -y update
apt-get -y dist-upgrade

# Vagrant essentials
packages=()
packages+=(htop nano git screen unison curl wget p7zip-full) # Basics
packages+=(dstat makepasswd traceroute nmap) # Utilities
packages+=(aufs-tools cgroup-lite) # Docker
apt-get -y install "${packages[@]}"

# Kill SSH messages
rm -f /etc/update-motd.d/*
service ssh restart


#
# Application setup
#

# Aquire containers and bin
cd /
curl --progress-bar https://storage.googleapis.com/scitran-dist/release.tar | tar x scitran/bin/ scitran/containers/
cd /scitran

# Install docker and venv
apt-get -y install docker.io python-virtualenv

# Use pinned docker binary to avoid docker-py throwing a tantrum
# TODO: be less absurd; building our own deb probably
#
# > Check this: https://github.com/jordansissel/fpm
# > IIRC, you can give fpm a source deb, make modifications to it, and output your own deb.
service docker.io stop
cp /scitran/bin/docker /usr/bin/docker
service docker.io start

# Install scitran
virtualenv venv
source venv/bin/activate
pip install -U pip setuptools
pip install -r requirements.txt

# Code
test -d code/api      || git clone https://github.com/scitran/api.git      code/api
test -d code/data     || git clone https://github.com/scitran/data.git     code/data
test -d code/sdm      || git clone https://github.com/scitran/sdm.git      code/sdm
test -d code/testdata || git clone https://github.com/scitran/testdata.git code/testdata

# Mongo does not like trying to memory-map files across operating systems.
# Place the persistent folder on the vagrant host.
# WILL DESTROY ANY STORED DATA IN THIS INSTANCE.
rm -rf /scitran/persistent
mkdir -p /var/persistent
ln -s /var/persistent /scitran/persistent

# Start in /scitran
echo "cd /scitran" >> /home/vagrant/.bashrc
