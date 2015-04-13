#!/bin/bash -e

# Prepare apt-get for usage
. /scitran/scripts/apt-get/update.sh

# Install pip
apt-get install -y python-dev python-pip git zlib1g-dev libjpeg-dev

# Install python packages
pip install numpy==1.9.0 \
	webapp2 webob requests markdown jsonschema \
	pymongo==2.7 \
	pillow \
	pytz \
	git+https://github.com/scitran/pydicom.gitmirror.git@value_mismatch \
	git+https://github.com/nipy/nibabel.git \
	git+https://github.com/moloney/dcmstack.git \
	uwsgi

# Cleanup
. /scitran/scripts/apt-get/clean.sh

