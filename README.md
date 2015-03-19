# SciTran &ndash; Scientific Data Management

## Installation

First, install the following depedencies:

- [Docker](https://docs.docker.com/installation)
- [Python2.7](https://www.python.org)
- [Python virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/)

Now, install SciTran:

```
curl https://storage.googleapis.com/scitran-dist/release.tar | tar x
virtualenv scitran/virtualenv
source scitran/virtualenv/bin/activate
pip install -U pip setuptools
pip install docker-py requests sh toml
```

Start SciTran:

```
sudo scitran/scitran.py start
```

## Development

If you plan to work on SciTran, clone this repository and install our dependencies:

```
git clone https://github.com/scitran/scitran.git
virtualenv scitran/virtualenv
source scitran/virtualenv/bin/activate
pip install -U pip setuptools
pip install docker-py requests sh toml
```

Download the release as above, but you only need two folders:

```
curl https://storage.googleapis.com/scitran-dist/release.tar | tar x scitran/bin/ scitran/containers/
```

Next, clone all our other source code:

```
git clone https://github.com/scitran/api.git      scitran/code/api
git clone https://github.com/scitran/data.git     scitran/code/data
git clone https://github.com/scitran/sdm.git      scitran/code/sdm
git clone https://github.com/scitran/testdata.git scitran/code/testdata

```

Finally, boot your local instance:

```
sudo scitran/scitran.py start
```
