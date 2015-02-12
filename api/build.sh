#!/bin/bash -e

# Prepare apt-get for usage
. /scitran/scripts/apt-get/update.sh

# Install pip
apt-get install -y python-dev python-pip git

# Install python packages
pip install numpy==1.9.0 \
	webapp2 webob requests markdown jsonschema \
	pymongo \
	pillow \
	git+https://github.com/scitran/pydicom.gitmirror.git@value_mismatch \
	git+https://github.com/nipy/nibabel.git \
	git+https://github.com/moloney/dcmstack.git \
	uwsgi

# Cleanup
. /scitran/scripts/apt-get/clean.sh

