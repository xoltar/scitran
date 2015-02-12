# Scitran

### Saving Science. Starting with Neuroscience.

## Installing

[Install Docker](https://docs.docker.com/installation), then download our release:

```
mkdir scitran ; cd scitran

wget https://storage.googleapis.com/scitran-dist/release.tar -O release.tar
tar -xf release.tar

sudo apt-get install -y python-pip
sudo pip install --target lib docker-py requests sh toml

sudo ./scitran.py start
```

## Development

If you plan to work on scitran, clone this repository and install our dependencies:

```
git clone https://github.com/scitran/scitran.git ; cd scitran

sudo apt-get install -y python-pip
sudo pip install --target lib docker-py requests sh toml
```

Download the release as above, but you only need the containers:

```
wget https://storage.googleapis.com/scitran-dist/release.tar -O release.tar
tar -xf release.tar containers/
```

Finally, clone all our other source code:

```
git clone https://github.com/scitran/api.git      code/api
git clone https://github.com/scitran/data.git     code/data
git clone https://github.com/scitran/scripts.git  code/scripts
git clone https://github.com/scitran/sdm.git      code/sdm
git clone https://github.com/scitran/testdata.git code/testdata

```

Finally, boot your local instance:

```
sudo ./scitran.py start
```
