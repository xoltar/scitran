#!/usr/bin/python

# pip install --target lib docker-py requests sh toml

# Ensure python can find the lib folder holding local packages
import sys,os
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))

# Stldib imports
import argparse, glob

# Local imports
import requests, sh, json
from docker import Client as DockerClient

# Run script from location of this script
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Setup
CONFIG_FILE = "config.json"
KEY_CERT_COMBINED_FILE = "key+cert.pem"
KEY_FILE="key.pem"
CERT_FILE="cert.pem"

FIG_IN=os.path.join("scripts", "templates", "fig.yml")
FIG_OUT=os.path.join("containers", "fig.yml")

CONFIGJS_IN=os.path.join("scripts", "templates", "config.js")
CONFIGJS_OUT=os.path.join("code", "sdm", "app", "config", "default", "config.js")

BOOTSTRAP_IN=os.path.join("scripts", "templates", "bootstrap.json")
BOOTSTRAP_OUT=os.path.join("api", "bootstrap.json")

# Ask the user a few questions about their new scitran instance, generate a config file
def interactiveGenerateConfig():

    docker=raw_input("Where's your docker daemon? (leave blank for default): ").strip()
    if docker == "":
        docker = "unix://var/run/docker.sock"

    domain=raw_input("\nEnter your domain name (or leave blank for a local install): ").strip()

    print "\nOptionally, you can run in demo mode."
    print "This will allow any user to login and user the system."
    demo=raw_input("Enable demo mode? (y/n): ").strip()

    # local installs have demo mode enabled
    # Local installs should NOT use 127.0.0.1 due to SSL problems :(
    if demo == "y":
        demo = '--demo'
    else:
        demo = ''

    if domain == "":
        domain = "localhost"

    print "\nDo you have a client authentication URL for your users?"
    clientAuthURL=raw_input("If so, enter it here (or leave blank for Google auth): ").strip()

    if clientAuthURL == "":
        clientAuthURL = "https://www.googleapis.com/plus/v1/people/me/openIdConnect"
        # client auth URL

    # Default empty values for a disconnected instance
    siteID=""
    siteName=""
    centralURL=""

    # If site is externally routable, ask if they're connected to scitran central
    if domain != "localhost":

        print "\nHave you registered this instance with Scitran Central?"
        siteID=raw_input("If so, enter the site ID here: ").strip()

        # Only needed if this instance is registered
        if siteID != "":
            centralURL="--central_uri https://sdmc.scitran.io/api"
            siteID = '--site_id ' + siteID
            siteName=raw_input("Enter your registered site name: ").strip()
        else:
            # site id is require, but can default to special reserved 'local'
            centralURL=""
            siteID="--site_id local"
            siteName="Local"

    # generate schema
    config = json.dumps({
        "docker": docker,
        "domain": domain,
        "demo": demo,
        "auth": {
            "provider": "Google",
            "server": {
                "authEndpoint": 'https://accounts.google.com/o/oauth2/auth',
                "verifyEndpoint": 'https://www.googleapis.com/oauth2/v1/tokeninfo',
            },
            "client": {
                "tokenEndpoint": clientAuthURL,
                "id": '528837662697-8ga3nnke42tl1hah312f7hddtl7p2uhe.apps.googleusercontent.com',
            }
        },
        "central" : {
            "url": centralURL,
            "id": siteID,
            "name": siteName,
        }
    }, indent=4, separators=(',', ': '))

    print "\nSaving config file to " + CONFIG_FILE + "..."
    configFile = open(CONFIG_FILE, "w")
    configFile.write(config)
    configFile.close()

# Generate a self-signed certificate
def createSelfSignedCert():

    print "Generating certificate with OpenSSL..."

    # OpenSSL will ask you some arbitrary set of questions, all of which are irrelevat for self-signed certificates. This feeds a large set of newlines in an attempt to brute-force ignore its prompts.
    input = []
    for x in range(0, 50):
        input.append("\n")

    # Generate individual files
    sh.openssl("req", "-x509", "-newkey", "rsa:2048", "-keyout", "key.pem", "-out", "cert.pem", "-days", "999", "-nodes", _in=input)

    if not (os.path.isfile(KEY_FILE) and os.path.isfile(CERT_FILE)):
        print "OpenSSL failed to generate both a " + KEY_FILE + " and a " + CERT_FILE + "."
        sys.exit(1)

    # Combine for our purposes
    key = open(KEY_FILE).read()
    cert = open(CERT_FILE).read()

    combined = open(KEY_CERT_COMBINED_FILE, "w")
    combined.write(key + cert)
    combined.close()

# Checks that there is exactly one container tarball matching a given name, and returns its location
def getTarball(name):
    matches = glob.glob('containers/' + name + '-*.tar.*')

    if len(matches) < 1:
        print "Could not find container " + name + " tarball. Are you sure your distribution download is valid?"
        sys.exit(1)
    elif len(matches) > 1:
        print "More than one copy of container " + name + " tarball, so we don't know which to install!"
        sys.exit(1)

    tarFile = matches[0]

    # String ops; format is ContainerType-VersionString.tar.Type
    base = os.path.basename(tarFile).rsplit(".", 3)[0]
    image = base.split("-", 1)
    imageName = "scitran-" + image[0]
    imageTag = image[1]

    return {
        "location": os.path.abspath(tarFile),
        "name": imageName,
        "tag": imageTag,
        "fullName": imageName + ":" + imageTag
    }

# Make a token effort to ensure all source directories have been cloned
def checkCodeDirs(dirs):
    for dir in dirs:
        if not os.path.isdir(os.path.join('code', dir)):
            print "\nCould not find the " + dir + " code."
            print "Are you sure your distribution download is valid?"
            print
            print "If you're a developer, try cloning this repository into the code/"+ dir + " folder."
            sys.exit(1)

# Generate config files with templated values
def generateTemplates(config):
    figTemplate = open(FIG_IN).read()
    fig = figTemplate.replace("SCITRAN-CWD", os.getcwd()).replace(
        "SCITRAN-AUTH-TOKEN-ENDPOINT", config['auth']['client']['tokenEndpoint']).replace(
        "SCITRAN-API-URL","https://" + config['domain'] + '/api').replace(
        "SCITRAN-SITE-ID",             config['central']['id']).replace(
        "SCITRAN-SITE-NAME",           config['central']['name']).replace(
        "SCITRAN-CENTRAL-URL",         config['central']['url']).replace(
        "SCITRAN-DEMO",                config['demo'])
    open(FIG_OUT, "w").write(fig)

    configJsTemplate = open(CONFIGJS_IN).read()
    configJs = configJsTemplate.replace(
        "SCITRAN-BASE-URL", "https://" + config["domain"] + "/api/").replace(
        "SCITRAN-AUTH-PROVIDER",        config['auth']['provider']).replace(
        "SCITRAN-AUTH-AUTHURL",         config['auth']['server']['authEndpoint']).replace(
        "SCITRAN-AUTH-VERIFYURL",       config['auth']['server']['verifyEndpoint']).replace(
        "SCITRAN-AUTH-CLIENTID",        config['auth']['client']['id'])
    open(CONFIGJS_OUT, "w").write(configJs)

    combinedCert = open(KEY_CERT_COMBINED_FILE).read()
    open(os.path.join("api", KEY_CERT_COMBINED_FILE), "w").write(combinedCert)
    open(os.path.join("nginx", KEY_CERT_COMBINED_FILE), "w").write(combinedCert)

# Hack for SH being weird.
def process_output(line):
    print line.strip()

def bootstrapData(config, docker, apiName, mongoName, email):
    # Set up a bootstrap.json with the user's email
    bootstrapTemplate = open(BOOTSTRAP_IN).read()
    bootstrap = bootstrapTemplate.replace("SCITRAN-EMAIL", email)
    open(BOOTSTRAP_OUT, "w").write(bootstrap)

    # Get the running api container
    mongoID = None
    nginxID = None
    for image in docker.containers():
        if mongoName in image['Image']:
            mongoID = image['Id']
        if 'nginx' in image['Image']:
            nginxID = image['Id']

    # Create a container for bootstrapping
    container = docker.create_container(
        image=apiName,
        working_dir="/service/code/api",
        environment={ "PYTHONPATH": "/service/code/data" },
        volumes=['/service/config', '/service/code'],
        command=["./bootstrap.py", "dbinitsort", "mongodb://mongo/nims", "/service/code/testdata/", "https://nginx/api", "-n", "-j", "/service/config/bootstrap.json"]
    )

    if container["Warnings"] != None:
        print container["Warnings"]

    # Run the container
    # NOTE: If these volumes change, scitran.py bootstrapping must as well.
    docker.start(container=container["Id"], links={mongoID: "mongo", nginxID: 'nginx'}, binds={
        os.path.join(os.getcwd(), 'api'):         {'bind': '/service/config', 'ro': False },
        os.path.join(os.getcwd(), 'code'):        {'bind': '/service/code',   'ro': False },
    })

    # Watch it run
    result = docker.logs(container=container["Id"], stream=True)
    for line in result:
        print line.strip()

    docker.remove_container(container=container["Id"])

# Create or upgrade, then start an instance of scitran
def start(args):
    print "Starting scitran..."

    # Resolve container downloads
    api = getTarball('api')
    mongo = getTarball('mongo')
    nginx = getTarball('nginx')

    # Resolve code installs
    checkCodeDirs(['api', 'data', 'sdm'])

    # Resolve configuration
    if not os.path.isfile(CONFIG_FILE):
        print "No config file found. Looks like we're setting up a new scitran instance today!\n"
        interactiveGenerateConfig()
    config = json.loads(open(CONFIG_FILE).read())

    # Resolve certificate
    if not os.path.isfile(KEY_CERT_COMBINED_FILE):
        print "\nNo certificate found.\nYou can either exit this script & save your own to " + KEY_CERT_COMBINED_FILE + " or let us generate one for you."
        raw_input("If a generated cert is OK, press enter to continue: ").strip()
        createSelfSignedCert()

    # Resolve local fig binary
    if not os.path.isfile(os.path.join("bin", "fig")):
        print "Could not find fig binary in the bin folder. Are you sure your distribution download is valid?"
        sys.exit(1)

    # Detect if cluster is new (has never been started before)
    newCluster = not os.path.isfile(os.path.join('data', 'mongo', 'mongod.lock'))
    email = ""

    # If cluster is brand new, run bootstrap instance
    if newCluster:
        print "\nIt looks like this is a new scitran instance. Would you like to add some data? "
        email = raw_input("If so, enter a valid " + config['auth']['provider'] + " email for your first user: ").strip()

    # Resolve docker daemon
    print "\nConnecting to docker..."
    docker = DockerClient(base_url=config['docker'])
    foundApi = False
    foundMongo = False
    foundNginx = False

    for image in docker.images():
        if api['fullName']   in image['RepoTags']:
            foundApi = True
        if mongo['fullName'] in image['RepoTags']:
            foundMongo = True
        if nginx['fullName'] in image['RepoTags']:
            foundNginx = True

    # Resolve imported containers
    if not foundApi:
        print "Importing api container..."
        docker.import_image(src=api['location'], repository=api['name'], tag=api['tag'])

    if not foundMongo:
        print "Importing mongo container..."
        docker.import_image(src=mongo['location'], repository=mongo['name'], tag=mongo['tag'])

    if not foundNginx:
        print "Importing nginx container..."
        docker.import_image(src=nginx['location'], repository=nginx['name'], tag=nginx['tag'])


    print "Confirming any previous scitran is stopped..."
    for image in docker.containers():
        if api['name']   in image['Image']:
            print "Stopping previous api..."
            docker.stop(container=image['Id'])
        if mongo['name'] in image['Image']:
            print "Stopping previous mongo..."
            docker.stop(container=image['Id'])
        if nginx['name'] in image['Image']:
            print "Stopping previous nginx..."
            docker.stop(container=image['Id'])

    print "Generating config files..."
    generateTemplates(config)

    print "Starting scitran..."
    fig = sh.Command("bin/fig")("-f", "containers/fig.yml", "-p", "scitran", "up", "-d", _out=process_output, _err=process_output)

    # Add new data if requested by user
    if newCluster and email != "":
        print "Adding initial data and user " + email + "..."
        bootstrapData(config, docker, api["fullName"], mongo["fullName"], email)

    print "\nCheck out your running site at https://" + config['domain']
    print "Scitran is running!"


# Stop a running scitran instance, if any
def stop(args):
    config = json.loads(open(CONFIG_FILE).read())
    docker = DockerClient(base_url=config['docker'])

    # Location of docker daemon could have changed; inform fig
    print "Generating config files..."
    generateTemplates(config)

    print "Stopping scitran..."
    for image in docker.containers():
        if "scitran-api"   in image['Image']:
            print "Stopping api..."
            docker.stop(container=image['Id'])
        if "scitran-mongo" in image['Image']:
            print "Stopping mongo..."
            docker.stop(container=image['Id'])
        if "scitran-nginx" in image['Image']:
            print "Stopping nginx..."
            docker.stop(container=image['Id'])


# Define an argument parser and run the valid function
def run():
    parser = argparse.ArgumentParser(prog='scitran.py')
    subparsers = parser.add_subparsers(help='sub-command help')

    # TODO: add unattended flag to guarantee no prompts (and fast-fail)
    # TODO: start without upgrade
    startParser = subparsers.add_parser('start', help='Start or upgrade scitran.')
    startParser.set_defaults(func=start)

    stopParser = subparsers.add_parser('stop', help='Stop scitran.')
    stopParser.set_defaults(func=stop)

    args = parser.parse_args()
    args.func(args)

# Run, ignoring ^C
try:
    run()
except requests.exceptions.ConnectionError, err:
    # Most likely a docker connection problem.
    print "\n", err , "\n"

    if "Permission denied" in str(err):
        print "You probably need to run this script as root."
    else:
        print "Check your connection and try again. Is docker running?"
        print "Docker installation instructions: https://docs.docker.com/installation"

    sys.exit(2)
except KeyboardInterrupt:
    pass
