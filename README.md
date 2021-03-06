# SciTran &ndash; Scientific Data Management

## Installation

First, install the following depedencies:

- [Docker](https://docs.docker.com/installation)
- [Python2.7](https://www.python.org)
- [Python virtualenv](http://docs.python-guide.org/en/latest/dev/virtualenvs/)

Second, register your instance with an Oauth2 provider.  Instructions below are for Google.

- go to https://console.developers.google.com
- create a new project, or select an existing project
- in the menu bar on the right side, click 'APIs & auth'
    - in 'APIs', enable the 'Google+' API
    - in 'Consent Screen', configure the 'Product Name' and 'email' fields
    - in 'Credentials', create a new Client ID for a web application
        - javascript origin: URL where you will access the webapp
            - example: https://domain.example.com/
        - redirect URI: Oauth2 callback URL
            - example: https://domain.example.com/components/authentication/oauth2callback.html
    - note the client-ID, you will be prompted for it during installation.

Now, install SciTran:

```
curl https://storage.googleapis.com/scitran-dist/release.tar | tar x
virtualenv scitran/venv
source scitran/venv/bin/activate
pip install -U pip setuptools
pip install -r scitran/requirements.txt
```

Start SciTran:

```
sudo scitran/scitran.py start
```

## Development

If you plan to work on SciTran, clone this repository and install our dependencies:

```
git clone https://github.com/scitran/scitran.git
virtualenv scitran/venv
source scitran/venv/bin/activate
pip install -U pip setuptools
pip install -r scitran/requirements.txt
```

Download the release as above, but you only need two folders:

```
curl https://storage.googleapis.com/scitran-dist/release.tar | tar x scitran/bin/ scitran/containers/
```

Next, clone all our other source code:

```
git clone https://github.com/scitran/api.git        scitran/code/api
git clone https://github.com/scitran/data.git       scitran/code/data
git clone https://github.com/scitran/sdm.git        scitran/code/sdm
git clone https://github.com/scitran/apps.git       scitran/code/apps
git clone https://github.com/scitran/testdata.git   scitran/code/testdata
git clone https://github.com/scitran/engine.git -b stopgap  scitran/code/engine

```

Finally, boot your local instance:

```
sudo scitran/scitran.py start
```

## Vagrant

You're welcome to try out vagrant box:

```
git clone https://github.com/scitran/scitran.git; cd scitran

vagrant up
vagrant ssh -c "sudo /scitran/scitran.py start"
```

This box currently assumes an empty + unconfigured scitran folder.
For filesystem compatibility reasons, the stateful `persistent` folder is placed at `/var/persistent` on the guest.

Do not use this method with pre-existing data or configuration; **it will be wiped**.


### Upgrading from before 0.2.2
Stop your instance, move `key+cert.pem` to `persistet/keys/base-key+cert.pem`, then restart your instance.

```
sudo scitran/scitran.py stop
mv scitran/key+cert.pem scitran/persistent/keys/base-key+cert.pem
sudo scitran/scitran.py start
```
