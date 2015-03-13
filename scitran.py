#!/usr/bin/env python
"""Entrypoint."""


# pip install --targ lib docker-py requests
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(os.path.join(HERE, 'lib'))

import re
import sh
import json
import toml
import glob
import docker
import shutil
import argparse
import subprocess
# import requests

# enforce run location
os.chdir(HERE)

# preflight
CONFIG_FILE = 'config.toml'
KEY_CERT_COMBINED_FILE = 'key+cert.pem'
KEY_FILE = 'key.pem'
CERT_FILE = 'cert.pem'

FIG_IN = os.path.join("scripts", "templates", "fig.yml")
FIG_OUT = os.path.join("containers", "fig.yml")

CONFIGJS_IN = os.path.join("scripts", "templates", "config.js")
CONFIGJS_OUT = os.path.join("code", "sdm", "app", "config", "default", "config.js")

BOOTSTRAP_IN = os.path.join("scripts", "templates", "bootstrap.json")
BOOTSTRAP_OUT = os.path.join("api", "bootstrap.json")


# building blocks
def generate_config():
    """Interactive configuration."""
    print 'Running interactice config'
    docker_url = 'unix://var/run/docker.sock'
    docker_url = raw_input('\nEnter your docker daemon URL? [%s]: ' % docker_url).strip() or docker_url

    domain = raw_input('\nEnter your domain name [localhost]: ').strip() or 'localhost'

    site_name = raw_input('\nEnter your site name [Local]: ').strip() or 'Local'

    print '\nOptionally, you can run in demo mode.'
    print 'This will allow any user of your auth provider to login and use the system'
    demo = False
    demo_mode = raw_input('Enable demo mode? (y/N): ').strip().lower() or 'n'
    if demo_mode in ['y', 'Y']:
        demo = True

    print '\nOptionally, you can run in insecure mode.'
    print 'This will make the api accept `user` as a url encoded param'
    insecure = False
    insecure_mode = raw_input('Enable insecure mode? [y/N]: ').strip().lower() or 'n'
    if insecure_mode in ['y', 'Y']:
        insecure = True

    # oauth2 id endpoint, endpoint that is granted for identity scope
    oa2_provider = 'Google'                                                             # js webapp
    oa2_id_endpoint = 'https://www.googleapis.com/plus/v1/people/me/openIdConnect'      # py api
    oa2_verify_endpoint = 'https://www.googleapis.com/oauth2/v1/tokeninfo'              # js webapp
    oa2_auth_endpoint = 'https://accounts.google.com/o/oauth2/auth'                     # js webapp
    oa2_client_id = '528837662697-8ga3nnke42tl1hah312f7hddtl7p2uhe.apps.googleusercontent.com'  # js webapp

    if (raw_input('\nUse %s as the oauth2 provider for your users [Y/n]? ' % oa2_provider).strip().lower() or 'y') == 'n':
        is_oa2_config = False
        while not is_oa2_config:
            oa2_provider = raw_input('Enter name of OAuth2 provider: ').strip()
            oa2_id_endpoint = raw_input('Enter OAuth2 ID endpoint: ').strip()
            oa2_verify_endpoint = raw_input('Enter OAuth2 Verification Endpoint: ').strip()

            print 'Register the following javascript origin and callback url with your provider:'
            print 'javascript origin: https://%s' % domain
            print 'callback url: https://%s/components/authentication/oauth2callback.html' % domain
            oa2_client_id = raw_input('Once registered, enter OAuth2 Client ID: ').strip()
            if oa2_provider and oa2_id_endpoint and oa2_verify_endpoint and oa2_client_id:
                is_oa2_config = True

    # scitran central
    # TODO: be able to set site id independly from central registration
    # desired behavior is to be able have whatever display in gui, regardless of being registered to internims
    site_id = 'local'
    registered = False
    if domain != 'localhost':
        print '\nHave you registered this site with scitran central?'
        site_id = raw_input('If so, enter your site ID []: ').strip() or site_id
    registered = True if site_id != 'local' else False

    # generage config dict
    config_dict = {
        'cwd': HERE,
        'docker_url': docker_url,
        'domain': domain,
        'demo': demo,
        'insecure': insecure,
        'site_id': site_id,
        'site_name': site_name,
        'auth': {
            'provider': oa2_provider,
            'id_endpoint': oa2_id_endpoint,
            'verify_endpoint': oa2_verify_endpoint,
            'auth_endpoint': oa2_auth_endpoint,
            'client_id': oa2_client_id,
        },
        'central': {
            'api_url': 'https://sdmc.scitran.io/api',
            'registered': registered,
        },
    }
    return config_dict


def system_report():
    """Get information about the system."""
    if not os.path.exists(CONFIG_FILE):
        print 'please configure docker client'
        sys.exit(2)

    config = read_config(CONFIG_FILE)
    sysname, nodename, release, version, machine = os.uname()
    docker_client_specs = docker.Client(config['docker_url']).version()
    _, _, ver, _, build = subprocess.check_output(['docker', '-v']).split()

    system_dict = {
        'sysname': sysname,
        'nodename': nodename,
        'release': release,
        'version': version,
        'machine': machine,
        'docker_client': docker_client_specs,
        'docker_server': {
            'ver': ver,
            'build': build,
        }
    }
    return system_dict


def write_config(config_dict, config_path):
    """Write config dictionary to json."""
    print '\nWriting configuration to %s' % config_path
    with open(config_path, 'w') as config_fp:
        config_fp.write(toml.dumps(config_dict))


def read_config(config_path):
    """Read config dictionary from json."""
    try:
        with open(config_path, 'r') as config_fp:
            return toml.loads(config_fp.read())
    except IOError as e:
        print 'Error reading configuration file. ' + str(e)
        print 'Please run `scitran config` or `scitran start`'
        sys.exit(2)
    else:
        print '\nLoaded configuration from %s' % config_path


def create_self_signed_cert():
    """Create selfsigned key+cert.pem."""
    print "Generating certificate with OpenSSL..."

    # OpenSSL will ask you some arbitrary set of questions, all of which are irrelevat for self-signed certificates.
    # This feeds a large set of newlines in an attempt to brute-force ignore its prompts.
    input = []
    for x in range(0, 50):
        input.append("\n")

    # Generate individual files
    sh.openssl("req", "-x509", "-newkey", "rsa:2048", "-keyout", KEY_FILE, "-out", CERT_FILE, "-days", "999", "-nodes", _in=input)

    if not (os.path.isfile(KEY_FILE) and os.path.isfile(CERT_FILE)):
        print "OpenSSL failed to generate both a " + KEY_FILE + " and a " + CERT_FILE + "."
        sys.exit(1)

    # Combine for our purposes
    key = open(KEY_FILE).read()
    cert = open(CERT_FILE).read()

    combined = open(KEY_CERT_COMBINED_FILE, "w")
    combined.write(key + cert)
    combined.close()

    if os.path.exists(KEY_CERT_COMBINED_FILE):
        print 'generated %s, %s and %s' % (KEY_FILE, CERT_FILE, KEY_CERT_COMBINED_FILE)


def generate_from_template(config_template_in, config_out):
    """Replace template placeholders with actual values."""
    print 'generating %s from %s x %s' % (config_out, config_template_in, CONFIG_FILE)
    config = read_config(CONFIG_FILE)
    rep = {
        'SCITRAN-CWD': config['cwd'],
        'SCITRAN-SITE-ID': config['site_id'],
        'SCITRAN-SITE-NAME': config['site_name'],
        'SCITRAN-API-URL': 'https://' + config['domain'] + '/api',
        'SCITRAN-CENTRAL-URL': ('--central_uri ' + config['central']['api_url']) if config['central']['registered'] else '',
        'SCITRAN-BASE-URL': 'https://' + config['domain'] + '/api/',
        'SCITRAN-DEMO': '--demo' if config['demo'] else '',
        'SCITRAN-INSECURE': '--insecure' if config['insecure'] else '',
        'SCITRAN-AUTH-PROVIDER': config['auth']['provider'],
        'SCITRAN-AUTH-ID-URL': config['auth']['id_endpoint'],
        'SCITRAN-AUTH-VERIFY-URL': config['auth']['verify_endpoint'],
        'SCITRAN-AUTH-AUTH-URL': config['auth']['auth_endpoint'],
        'SCITRAN-AUTH-CLIENTID': config['auth']['client_id'],
    }
    rep = dict((re.escape(k), v) for k, v in rep.iteritems())
    pattern = re.compile("|".join(rep.keys()))
    text = None
    with open(config_template_in, 'r') as template:
        text = pattern.sub(lambda m: rep[re.escape(m.group(0))], template.read())
        with open(config_out, 'w') as output:
            output.write(text)

    if os.path.exists(config_out):
        print 'created %s' % config_out


def getTarball(name):
    """Collect information about an image from the corresponding tarball."""
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


def bootstrap_data(args, api_name, mongo_name, email):
    """Bootstrap the installation by adding first user and uploading testdata."""
    bootstrap_template = open(BOOTSTRAP_IN).read()
    with open(BOOTSTRAP_OUT, 'w') as bootstrap:
        bootstrap.write(bootstrap_template.replace('SCITRAN-EMAIL', email))

    config = read_config(CONFIG_FILE)
    c = docker.Client(config['docker_url'])

    # Get the running api container
    mongo_id = None
    nginx_id = None
    for image in c.containers():
        if mongo_name in image['Image']:
            mongo_id = image['Id']
        if 'nginx' in image['Image']:
            nginx_id = image['Id']

    # Create a container for bootstrapping
    container = c.create_container(
        image=api_name,
        working_dir="/service/code/api",
        environment={"PYTHONPATH": "/service/code/data"},
        volumes=['/service/config', '/service/code'],
        command=["./bootstrap.py", "dbinitsort", "mongodb://mongo/scitran", "/service/code/testdata/", "https://nginx/api", "-n", "-j", "/service/config/bootstrap.json"]
    )

    if container["Warnings"] is not None:
        print container["Warnings"]

    # Run the container
    # NOTE: If these volumes change, scitran.py bootstrapping must as well.
    c.start(container=container["Id"], links={mongo_id: "mongo", nginx_id: 'nginx'}, binds={
        os.path.join(HERE, 'api'):         {'bind': '/service/config', 'ro': False },
        os.path.join(HERE, 'code'):        {'bind': '/service/code',   'ro': False },
    })

    # Watch it run
    result = c.logs(container=container["Id"], stream=True)
    for line in result:
        print line.strip()

    c.remove_container(container=container["Id"])


def instance_status():
    """Show which containers are running."""
    config = read_config(CONFIG_FILE)
    status = {
        'scitran-api': {
            'status': 'not running',
        },
        'scitran-mongo': {
            'status': 'not running',
        },
        'scitran-nginx': {
            'status': 'not running',
        },
    }
    # TODO parse the output of docker inspect
    for container in docker.Client(config['docker_url']).containers():
        # TODO parse the container information
        for image_name in ['scitran-api', 'scitran-mongo', 'scitran-nginx']:
            if image_name in container['Image']:
                # TODO add more details!
                status_item = status[image_name]
                status_item['status'] = 'running'
                status_item['ports'] = container['Ports']
                status_item['status'] = container['Status']
                status_item['Image'] = container['Image']
    return status


# targets
def start(args):
    """Start or restart the scitran instance."""
    print '\n(re)starting the instance'
    def process_output(line):
        print line.strip()

    # Resolve local fig binary
    if not os.path.isfile(os.path.join("bin", "fig")):
        print "Could not find fig binary in the bin folder. Are you sure your distribution download is valid?"
        sys.exit(1)

    # load config
    if not os.path.exists(CONFIG_FILE):
        write_config(generate_config(), CONFIG_FILE)
    config = read_config(CONFIG_FILE)

    # key+cert.pem check
    if not os.path.exists(KEY_CERT_COMBINED_FILE):
        print "\nNo certificate found."
        print "You can either exit this script & save your own to " + KEY_CERT_COMBINED_FILE
        print "or let us generate one for you."
        raw_input("If a generated cert is OK, press enter to continue: ").strip()
        create_self_signed_cert()

    # copy key+cert.pem into locations that will be bind mounted to the containers
    print 'Copying key+cert.pem into api and nginx bind mount locations'
    combinedCert = open(KEY_CERT_COMBINED_FILE).read()
    open(os.path.join("api", KEY_CERT_COMBINED_FILE), "w").write(combinedCert)
    open(os.path.join("nginx", KEY_CERT_COMBINED_FILE), "w").write(combinedCert)

    # Detect if cluster is new (has never been started before)
    newCluster = not os.path.isfile(os.path.join('persistent', 'mongo', 'mongod.lock'))
    email = ""
    if newCluster:
        print "\nIt looks like this is a new scitran instance. Would you like to add some data? "
        email = raw_input("If so, enter a valid " + config['auth']['provider'] + " email for your first user: ").strip()
    print email

    # Resolve container downloads
    api = getTarball('api')
    mongo = getTarball('mongo')
    nginx = getTarball('nginx')

    # Resolve docker daemon
    print "\nConnecting to docker..."
    docker_client = docker.Client(base_url=config['docker_url'])
    foundApi = False
    foundMongo = False
    foundNginx = False

    for image in docker_client.images():
        if api['fullName'] in image['RepoTags']:
            foundApi = True
        if mongo['fullName'] in image['RepoTags']:
            foundMongo = True
        if nginx['fullName'] in image['RepoTags']:
            foundNginx = True

    # Resolve imported containers
    if not foundApi:
        print "Importing api container..."
        docker_client.import_image(src=api['location'], repository=api['name'], tag=api['tag'])

    if not foundMongo:
        print "Importing mongo container..."
        docker_client.import_image(src=mongo['location'], repository=mongo['name'], tag=mongo['tag'])

    if not foundNginx:
        print "Importing nginx container..."
        docker_client.import_image(src=nginx['location'], repository=nginx['name'], tag=nginx['tag'])

    # generate config files
    generate_from_template(CONFIGJS_IN, CONFIGJS_OUT)
    generate_from_template(FIG_IN, FIG_OUT)

    # start the containers
    print "Starting scitran..."
    fig = sh.Command("bin/fig")("-f", "containers/fig.yml", "-p", "scitran", "up", "-d", _out=process_output, _err=process_output)

    # also spin up a service container
    print "Starting a service container..."

    # Add new data if requested by user
    if newCluster and email != "":
        print "Adding initial data and user " + email + "..."
        bootstrap_data(args, api["fullName"], mongo["fullName"], email)

    # check the state of the instance, are all three containers running?
    # TODO: instead of checking that three containers are running try hitting the API with requests. HEAD /api
    current_status = instance_status()
    running = 0
    for k, v in current_status.iteritems():
        if current_status[k]['status'] != 'not running':
            running += 1
    if running == 3:
        print "\nCheck out your running site at https://" + config['domain']
        print "Scitran is running!"
    else:
        print '\nSomething went wrong...'


def stop(args):
    """Stop a running instance."""
    config = read_config(CONFIG_FILE)
    docker_client = docker.Client(base_url=config['docker_url'])
    for image in docker_client.containers():
        # TODO: parse these names from the fig file
        for image_name in ['scitran-api', 'scitran-mongo', 'scitran-nginx']:
            if image_name in image['Image']:
                print "Stopping previous %s..." % image_name
                docker_client.stop(container=image['Id'])
    # TODO: stop should also clear out the containers that were being used

def inspect(args):
    pass

def build(args):
    pass

def bugreport(args):
    pass

def service(args):
    """Print the command line to start a maintenance container."""
    current_status = instance_status()
    print 'docker -it --link scitran_mongo_1:mongo scitran-api:0 /bin/bash'

def system(args):
    print json.dumps(system_report(), indent=4, separators=(',', ': '))

def status(args):
    print json.dumps(instance_status(), indent=4, separators=(',', ': '))

def size(args):
    """Display the size of the persistent storage."""
    # TODO: convert to python
    sizes = {}
    for l in subprocess.check_output(['du', '-h', '-d 1', 'persistent']).split('\n'):
        if l:
            size, path = l.split()
            sizes[path] = size
    print json.dumps(sizes, indent=4, separators=(',', ': '))

def config(args):
    """Rerun, view, or remove the configuration."""
    if args.action == 'rm':
        print 'Removing config.json'
        os.remove(CONFIG_FILE)
    elif args.action == 'view':
        print json.dumps(read_config(CONFIG_FILE), indent=5, separators=(',', ': '))
    else:
        if os.path.exists(CONFIG_FILE):
            print 'warning: config.json exists'
            if raw_input('Rerun config and obliterate old config.json? [y/N]: ').strip().lower() == 'y':
                write_config(generate_config(), CONFIG_FILE)
        else:
            write_config(generate_config(), CONFIG_FILE)

def purge(args):
    print '\nWARNING: PURGING'
    # TODO make sure this instance's containers are stopped
    if os.path.exists('config.json'):
        os.remove('config.json')
        print 'purged ./config.json'
    try:
        shutil.rmtree('persistent')
    except OSError as e:
        print str(e)
        print 'Are you `tail`ing any log files? or have any files open? please close and rerun `./scitran.py purge`'
    else:
        print 'purged ./persistent/'

    # TODO remove the containers
    # TODO remove the images

if __name__ == '__main__':
    # entrypoints
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help='operation to perform')

    # start
    start_parser = subparsers.add_parser(
        name='start',
        help='start or restart',
        description='scitran start',
        )
    start_parser.set_defaults(func=start)

    # stop
    stop_parser = subparsers.add_parser(
        name='stop',
        help='stop',
        description='scitran stop',
        )
    stop_parser.set_defaults(func=stop)

    # inspect
    inspect_parser = subparsers.add_parser(
        name='inspect',
        help='inspect the instance',
        description='scitran inspect',
        )
    inspect_parser.set_defaults(func=inspect)

    # bugreport
    bugreport_parser = subparsers.add_parser(
        name='bugreport',
        help='create bug report',
        description='scitran bugreport',
        )
    bugreport_parser.set_defaults(func=bugreport)

    # system
    system_parser = subparsers.add_parser(
        name='system',
        help='show system details',
        description='scitran system',
        )
    system_parser.set_defaults(func=system)

    # service
    service_parser = subparsers.add_parser(
        name='service',
        help='show status of instance',
        description='scitran status',
        )
    service_parser.set_defaults(func=service)

    # status
    status_parser = subparsers.add_parser(
        name='status',
        help='show status of instance',
        description='scitran status',
        )
    status_parser.set_defaults(func=status)

    # size
    size_parser = subparsers.add_parser(
        name='size',
        help='show size information',
        description='scitran size',
        )
    size_parser.set_defaults(func=size)

    # config
    config_parser = subparsers.add_parser(
        name='config',
        help='configure',
        description='scitran config',
        )
    config_parser.add_argument('action', help='view', choices=['rerun', 'rm', 'view'], nargs='?', default='rerun')
    config_parser.set_defaults(func=config)

    purge_parser = subparsers.add_parser(
        name='purge',
        help='remove scitan config, persistent data, containers and images. BRUTAL!',
        description='./scitran.py purge',
        )
    purge_parser.set_defaults(func=purge)

    # do it
    args = parser.parse_args()
    args.func(args)
