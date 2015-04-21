#!/usr/bin/env python
"""Manage a SciTran installation."""


# pip install --targ lib docker-py requests
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VENV = os.path.join(HERE, 'venv/lib/python2.7/site-packages')
venv_setup_cmds = """
cd %s
virtualenv venv
source venv/bin/activate
pip install -U pip setuptools
pip install docker-py requests toml sh
""" % HERE

if os.path.isdir(VENV):
    sys.path.insert(0, VENV)
else:
    print '\nvirtualenv "venv" not found. Please run the following commands:'
    print venv_setup_cmds
    sys.exit(1)

try:
    import re
    import sh
    import json
    import toml
    import glob
    import docker
    import shutil
    import hashlib
    import argparse
    import subprocess
    import requests
except ImportError as e:
    print str(e) + '. Please run the following commands:'
    print venv_setup_cmds
    sys.exit(1)

requests.packages.urllib3.disable_warnings()

# enforce run location
os.chdir(HERE)

# preflight
CONFIG_FILE = 'config.toml'

KEYS_FOLDER = os.path.join('persistent', 'keys')

KEY_CERT_COMBINED_FILE =   os.path.join(KEYS_FOLDER, 'base-key+cert.pem')
KEY_FILE =                 os.path.join(KEYS_FOLDER, 'base-key.pem')
CERT_FILE =                os.path.join(KEYS_FOLDER, 'base-cert.pem')

ROOT_CERT_COMBINED_FILE  = os.path.join(KEYS_FOLDER, 'rootCA-key+cert.pem')
ROOT_KEY_FILE =            os.path.join(KEYS_FOLDER, 'rootCA-key.pem')
ROOT_CERT_FILE =           os.path.join(KEYS_FOLDER, 'rootCA-cert.pem')
ROOT_SRL_FILE =            os.path.join(KEYS_FOLDER, 'rootCA-cert.srl')

FIG_IN = os.path.join("scripts", "templates", "fig.yml")
FIG_OUT = os.path.join("containers", "fig.yml")

CONFIGJS_IN = os.path.join("scripts", "templates", "config.js")
CONFIGJS_OUT = os.path.join("code", "sdm", "app", "config", "default", "config.js")

BOOTSTRAP_IN = os.path.join("scripts", "templates", "bootstrap.json")
BOOTSTRAP_OUT = os.path.join("api", "bootstrap.json")


# building blocks
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


def process_output(line):
    """Handler for formatting output from sh.Command."""
    print line.strip()


def generate_config(mode='default'):
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
    oa2_client_id = '1052740023071-n20pk8h5uepdua3r8971pc6jrf25lvee.apps.googleusercontent.com'  # js webapp

    if (raw_input('\nUse %s as the oauth2 provider for your users [Y/n]? ' % oa2_provider).strip().lower() or 'y') == 'n':
        is_oa2_config = False
        while not is_oa2_config:
            oa2_provider = raw_input('Enter name of OAuth2 provider: ').strip()
            oa2_id_endpoint = raw_input('Enter OAuth2 ID endpoint: ').strip()
            oa2_verify_endpoint = raw_input('Enter OAuth2 Verification Endpoint: ').strip()

            print 'Register the following javascript origin and callback url with your provider:'
            print 'javascript origin: https://%s' % domain
            print 'callback url: https://%s/components/authentication/oauth2callback.html' % domain
            if oa2_provider and oa2_id_endpoint and oa2_verify_endpoint:
                is_oa2_config = True

    oa2_client_id = raw_input('Enter your project OAuth2 Client ID: ').strip() or oa2_client_id

    # scitran central
    registered = False
    if domain != 'localhost':
        registered = raw_input('\nHave you registered with scitran central [y/N]: ').strip().lower() == 'y'

    site_id = raw_input('\nEnter your site ID [local]: ').strip() or 'local'

    http_port = 80
    https_port = 443
    machine_port = 8080
    ssl_terminator = False
    uwsgi_processes = 4
    mongo_path = 'persistent/mongo'
    data_path = 'persistent/data'
    if mode == 'advanced':
        print('\nExpert Mode Configurations')
        http_port = int(raw_input('http port [%s]: ' % http_port).strip() or http_port)
        https_port = int(raw_input('https port [443]: ').strip() or https_port)
        machine_port = int(raw_input('machine api [8080]: ').strip()or machine_port)
        ssl_terminator = (raw_input('serve behind ssl terminator? [N/y]: ').strip().lower() == 'y')
        uwsgi_processes = int(raw_input('number of uwsgi processes? [4]: ').strip() or uwsgi_processes)
        mongo_path = raw_input('path to mongodb [%s]: ' % mongo_path).strip() or mongo_path
        data_path = raw_input('path to data: [%s]: ' % data_path).strip() or data_path
        # TODO: nginx worker processes, uwsgi master/threads/processes, etc.

    # generage config dict
    config_dict = {
        'docker_url': docker_url,
        'domain': domain,
        'demo': demo,
        'insecure': insecure,
        'fig_prefix': site_id.replace('_', ''),
        'site_id': site_id,
        'site_name': site_name,
        'http_port': http_port,
        'https_port': https_port,
        'machine_port': machine_port,
        'ssl_terminator': ssl_terminator,
        'uwsgi_processes': uwsgi_processes,
        'storage': {
            'mongo_path': mongo_path,
            'data_path': data_path,
        },
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
    sizes = {}
    for l in subprocess.check_output(['du', '-h', '-d 1', 'persistent']).split('\n'):
        if l:
            size, path = l.split()
            sizes[path] = size

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
        },
        'disk_usage': sizes,
        'configuration': config,
    }
    return system_dict


def create_self_certificate_authority(force=False):
    """Create our own certificate authority."""
    if os.path.exists(ROOT_CERT_COMBINED_FILE) and not force:
        print('\n\nWARNING!  WARNING!')
        print('\n%s already exists. Replacing this file will invalidate')
        print('any existing client certificates. You will need to recreate')
        print('all client certificates.')
        confirm = raw_input('Are you sure you wish to continue? [y/N]: ') or 'n'
        if confirm.lower() == 'y':
            create_self_certificate_authority(force=True)
    input_ = ['\n'] * 50
    sh.openssl('genrsa', '-out', ROOT_KEY_FILE, '2048')
    sh.openssl('req', '-x509', '-new', '-nodes', '-key', ROOT_KEY_FILE, '-days', '999', '-out', ROOT_CERT_FILE, _in=input_)
    # now join two to give to nginx
    key = open(ROOT_KEY_FILE).read()
    cert = open(ROOT_CERT_FILE).read()
    combined = open(ROOT_CERT_COMBINED_FILE, "w")
    combined.write(key + cert)
    combined.close()


def create_client_cert(drone_name):
    """
    Create a new client certificate from the specified drone.

    Each of the signed certs must have a complete DN to be valid, including common name.
    However, the common name does not need to match the match with the drone.  This is a
    reminder that nginx is verifying the certificate is signed by a trusted CA, it does not
    performs reverse look-up to verify the hostname.
    """
    input_ = ['\n'] * 5 + ['localhost\n'] + (['\n'] * 30)
    drone_key =      os.path.join('persistent', 'keys', 'client-%s-key.pem'      % drone_name)
    drone_cert =     os.path.join('persistent', 'keys', 'client-%s-cert.pem'     % drone_name)
    drone_csr =      os.path.join('persistent', 'keys', 'client-%s.csr'          % drone_name)
    drone_combined = os.path.join('persistent', 'keys', 'client-%s-key+cert.pem' % drone_name)
    sh.openssl('genrsa', '-out', drone_key, '2048')
    sh.openssl('req', '-new', '-key', drone_key, '-out', drone_csr, _in=input_)
    if not os.path.exists(ROOT_SRL_FILE):
        print 'creating new CA serial file'
        cmd = ['x509', '-req', '-in', drone_csr, '-CA', ROOT_CERT_FILE, '-CAkey', ROOT_KEY_FILE, '-CAcreateserial', '-out', drone_cert, '-days', '999']
    else:
        print 'reusing exisitng CA serial file'
        cmd = ['x509', '-req', '-in', drone_csr, '-CA', ROOT_CERT_FILE, '-CAkey', ROOT_KEY_FILE, '-CAserial', ROOT_SRL_FILE, '-out', drone_cert, '-days', '999']
    sh.openssl(cmd)
    key = open(drone_key).read()
    cert = open(drone_cert).read()

    combined = open(drone_combined, "w")
    combined.write(key + cert)
    combined.close()

    print '\ngenerated %s' % drone_combined

    # After signing, the CSR is useless
    os.remove(drone_csr)


def create_self_signed_cert():
    """Create self signed key+cert.pem."""
    print "Generating certificate with OpenSSL..."

    # Folder to hold all client certificates
    if not os.path.exists(KEYS_FOLDER): os.makedirs(KEYS_FOLDER)

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


def generate_from_template(config_template_in, config_out, nginx_image='', api_image='', mongo_image=''):
    """Replace template placeholders with actual values."""
    print 'generating %s from %s x %s' % (config_out, config_template_in, CONFIG_FILE)
    config = read_config(CONFIG_FILE)
    rep = {
        'SCITRAN-HTTP-PORT': str(config['http_port']),
        'SCITRAN-HTTPS-PORT': str(config['https_port']),
        'SCITRAN-MACHINE-PORT': str(config['machine_port']),
        'SCITRAN-UWSGI-PROCESSES': str(config['uwsgi_processes']),
        'SCITRAN-NGINX-IMAGE': nginx_image,
        'SCITRAN-API-IMAGE': api_image,
        'SCITRAN-MONGO-IMAGE': mongo_image,
        'SCITRAN-CWD': HERE,
        'SCITRAN-DATA-PATH': config['storage']['data_path'],
        'SCITRAN-MONGO-PATH': config['storage']['mongo_path'],
        'SCITRAN-SITE-ID': config['site_id'],
        'SCITRAN-SITE-NAME': config['site_name'],
        'SCITRAN-API-URL': 'https://' + config['domain'] + ':8080' + '/api',
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
    base = os.path.basename(tarFile).split('.tar')[0]
    image = base.split("-", 1)
    imageName = "scitran-" + image[0]
    imageTag = image[1]

    return {
        "location": os.path.abspath(tarFile),
        "name": imageName,
        "tag": imageTag,
        "fullName": imageName + ":" + imageTag
    }


def configure_json(args=None, target=None):
    """Prepare a bootstrap.json for db bootstrapping."""
    if target or (raw_input('Do you have a bootstrap.json you would like to use? [y/N]').strip().lower() == 'y'):
        target = raw_input('Enter the path of your bootstrap json file: ').strip()
        print ('bootstrap file, %s, will be copied to %s' % (target, BOOTSTRAP_OUT))
        shutil.copy(target, BOOTSTRAP_OUT)
    else:  # generate a bootstrap from template.
        print 'It\'s okay.  We can make a bootstrap json file for you.'
        overwrite = True
        if os.path.exists(BOOTSTRAP_OUT):
            overwrite = raw_input('bootstrap file exists, overwrite? [y/N]:').strip().lower() == 'y'
        if overwrite:
            config = read_config(CONFIG_FILE)
            email = None
            while not email:
                email = raw_input('Please enter a %s email address for your first user: ' % config['auth']['provider']).strip()
            bootstrap_template = open(BOOTSTRAP_IN).read()
            with open(BOOTSTRAP_OUT, 'w') as bootstrap:
                bootstrap.write(bootstrap_template.replace('SCITRAN-EMAIL', email))


def configure_certificate(args=None, target=None):
    """Prepare the instance ssl key+cert pem file."""
    if target or (raw_input('Do you have an existing key+cert.pem you would like to use? [y/N]').strip().lower() == 'y'):
        target = raw_input('Enter the path of your key+cert.pem file: ').strip()
        print ('key+cert.pem, %s, will be copied to %s' % (target, KEY_CERT_COMBINED_FILE))
        shutil.copy(target, KEY_CERT_COMBINED_FILE)
    else:
        print 'Generating a self-signed SSL %s certificate...' % KEY_CERT_COMBINED_FILE
        create_self_signed_cert()


def configure_CA(args=None, target_key=None, target_cert=None, target_combined=None):
    """Prepare the instance CA authority."""
    has_all = (target_key and target_cert and target_combined)
    if has_all or (raw_input('Do you have an existing CA certificate you would like to use?').strip().lower() == 'y'):
        target_key = raw_input('Enter the path of your CA key pem: ').strip().lower()
        target_cert = raw_input('Enter the path of your CA certificate pem: ').strip().lower()
        target_combined = raw_input('Enter the path of your CA key+certificate pem: ').strip().lower()
        shutil.copy(target_key, ROOT_KEY_FILE)
        shutil.copy(target_cert, ROOT_CERT_FILE)
        shutil.copy(target_combined, ROOT_CERT_COMBINED_FILE)
    else:
        print '\nGenerating a self-signed root Certificate Authority'  # TODO better wording, more helpful text
        create_self_certificate_authority()


def bootstrap_db(args=None):
    """Bootstrap the database using the bootstrap.json file."""
    if not (raw_input('Would you like to bootstrap the database? [Y/n]: ').strip().lower() or 'y') == 'y':
        print 'skipping database bootstrapping'
        return

    config = read_config(CONFIG_FILE)
    fig_prefix = config.get('fig_prefix')
    c = docker.Client(config['docker_url'])
    api_name = getTarball('api')['fullName']
    # Get the running api container
    mongo_id = None
    nginx_id = None
    for container in c.containers():
        if '/%s_mongo_1' % fig_prefix in container['Names']:
            mongo_id = container['Id']
        if '/%s_nginx_1' % fig_prefix in container['Names']:
            nginx_id = container['Id']

    cmd = ["./bootstrap.py", "dbinit", "mongodb://mongo/scitran", "-j", "/service/config/bootstrap.json"]
    if args and args.force:
        cmd = ["./bootstrap.py", "dbinit", "mongodb://mongo/scitran", "-f", "-j", "/service/config/bootstrap.json"]

    # Create a container for bootstrapping
    container = c.create_container(
        image=api_name,
        working_dir="/service/code/api",
        environment={"PYTHONPATH": "/service/code/data"},
        volumes=['/service/config', '/service/code'],
        command=cmd,
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
    pass


def bootstrap_apps(args=None):
    """Bootstrap the installation by adding an application. This should occur before bootstrapping data."""
    if not (raw_input('Would you like to bootstrap apps? [Y/n]: ').strip().lower() or 'y')== 'y':
        print 'skipping apps bootstrapping'
        return

    config = read_config(CONFIG_FILE)
    fig_prefix = config.get('fig_prefix')
    c = docker.Client(config['docker_url'])
    api_name = getTarball('api')['fullName']
    # Get the running api container
    mongo_id = None
    nginx_id = None
    for container in c.containers():
        if '/%s_mongo_1' % fig_prefix in container['Names']:
            mongo_id = container['Id']
        if '/%s_nginx_1' % fig_prefix in container['Names']:
            nginx_id = container['Id']

    # Create a container for bootstrapping
    container = c.create_container(
        image=api_name,
        working_dir="/service/code/api",
        environment={"PYTHONPATH": "/service/code/data"},
        volumes=['/service/config', '/service/code', '/service/data'],
        command=["./bootstrap.py", "appsinit", "mongodb://mongo/scitran", "/service/code/apps/dcm_convert", "/service/apps"]
    )

    if container["Warnings"] is not None:
        print container["Warnings"]

    # Run the container
    # NOTE: If these volumes change, scitran.py bootstrapping must as well.
    c.start(container=container["Id"], links={mongo_id: "mongo", nginx_id: 'nginx'}, binds={
        os.path.join(HERE, 'api'):              {'bind': '/service/config', 'ro': False },
        os.path.join(HERE, 'code'):             {'bind': '/service/code',   'ro': False },
        os.path.join(HERE, 'persistent/apps'):  {'bind': '/service/apps',   'ro': False },
    })

    # Watch it run
    result = c.logs(container=container["Id"], stream=True)
    for line in result:
        print line.strip()

    c.remove_container(container=container["Id"])


def bootstrap_data(args=None, mode='upload', bootstrap_path=os.path.join(HERE, 'code', 'testdata')):
    """
    Upload data.

    These must take a 'path' as input.  where to get the data from.
    """
    if not (raw_input('Would you like to bootstrap data from %s? [Y/n]: ' % bootstrap_path).strip().lower() or 'y') == 'y':
        if raw_input('Would you like to bootstrap data from a different location? [y/N]: ').strip().lower() == 'y':
            bootstrap_path = ''
            while not os.path.exists(bootstrap_path) and not os.path.isabs(bootstrap_path):
                bootstrap_path = raw_input('Enter the directory path that contains your data: ').strip().lower()
        else:
            print 'skipping bootstrapping data.'
            return

    api_name = getTarball('api')['fullName']
    config = read_config(CONFIG_FILE)
    fig_prefix = config.get('fig_prefix')
    c = docker.Client(config['docker_url'])

    if not os.path.isabs(bootstrap_path):
        print '\nERROR: expected absolute path to bootstrap data'
    if not os.path.exists(bootstrap_path):
        print '\nERROR: dirpath %s could not be found' % bootstrap_path

    # Get the running api container
    mongo_id = None
    nginx_id = None
    for container in c.containers():
        if '/%s_mongo_1' % fig_prefix in container['Names']:
            mongo_id = container['Id']
        if '/%s_nginx_1' % fig_prefix in container['Names']:
            nginx_id = container['Id']

    upload_url = 'https://nginx/api'
    if config.get('ssl_terminator'):
        upload_url = 'http://nginx/api'

    if mode == 'upload':
        command = ["./bootstrap.py", "upload", "/bootstrap_path", upload_url, "-n"]
    elif mode == 'sort':
        command = ["./bootstrap.py", "sort", "mongodb://mongo/scitran", "/bootstrap_path", "/service/data"]

    # TODO: expose upload vs sort
    # Create a container for bootstrapping
    container = c.create_container(
        image=api_name,
        working_dir="/service/code/api",
        environment={"PYTHONPATH": "/service/code/data"},
        volumes=['/service/config', '/service/code', '/service/data', '/bootstrap_path'],
        command=command,
    )

    if container["Warnings"] is not None:
        print container["Warnings"]

    # Run the container
    # NOTE: If these volumes change, scitran.py bootstrapping must as well.
    c.start(container=container["Id"], links={mongo_id: "mongo", nginx_id: 'nginx'}, binds={
        os.path.join(HERE, 'api'):          {'bind': '/service/config', 'ro': False},
        os.path.join(HERE, 'code'):         {'bind': '/service/code',   'ro': False},
        config['storage']['data_path']:     {'bind': '/service/data',   'ro': False},
        bootstrap_path:                     {'bind': '/bootstrap_path', 'ro': False},
    })

    # Watch it run
    result = c.logs(container=container["Id"], stream=True)
    for line in result:
        print line.strip()

    c.remove_container(container=container["Id"])


def bootstrap(args):
    """Select bootstrap operation to perform."""
    if not args.db and not args.apps and not args.data:
        print '\nPlease specify a bootstrapping taget, --db, --apps, or --data'
    if args.db:
        configure_json()
        bootstrap_db(args)
    if args.apps:
        bootstrap_apps(args)
    if args.data:
        bootstrap_data(args)


def instance_status():
    """Show which containers are running."""
    config = read_config(CONFIG_FILE)
    fig_prefix = config.get('fig_prefix')
    status = {
        '/%s_api_1' % fig_prefix: {
            'status': 'not running',
        },
        '/%s_mongo_1' % fig_prefix: {
            'status': 'not running',
        },
        '/%s_nginx_1' % fig_prefix: {
            'status': 'not running',
        },
        '/%s_maintenance_1' % fig_prefix: {
            'status': 'not running',
        },
    }
    # TODO parse the output of docker inspect
    for container in docker.Client(config['docker_url']).containers():
        # TODO parse the container information
        for container_name in status.keys():
            if container_name in container['Names']:
                # TODO add more details!
                status_item = status[container_name]
                status_item['status'] = 'running'
                status_item['ports'] = container['Ports']
                status_item['status'] = container['Status']
                status_item['Image'] = container['Image']
    return status


# targets
def start(args):
    """Start or restart the scitran instance."""
    print '\n(re)starting the instance'
    # Resolve local fig binary
    if not os.path.isfile(os.path.join("bin", "fig")):
        print "Could not find fig binary in the bin folder. Are you sure your distribution download is valid?"
        sys.exit(1)

    # load config
    if not os.path.exists(CONFIG_FILE):
        write_config(generate_config(mode=args.mode), CONFIG_FILE)
    config = read_config(CONFIG_FILE)

    # Resolve container downloads
    api = getTarball('api')
    mongo = getTarball('mongo')
    nginx = getTarball('nginx')
    maintenance = getTarball('maintenance')

    # Resolve docker daemon
    print "\nConnecting to docker..."
    docker_client = docker.Client(base_url=config['docker_url'])
    foundApi = False
    foundMongo = False
    foundNginx = False
    foundMaintenance = False

    for image in docker_client.images():
        if api['fullName'] in image['RepoTags']:
            foundApi = True
        if mongo['fullName'] in image['RepoTags']:
            foundMongo = True
        if nginx['fullName'] in image['RepoTags']:
            foundNginx = True
        if maintenance['fullName'] in image['RepoTags']:
            foundMaintenance = True

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

    if not foundMaintenance:
        print "Importing maintenance container..."
        docker_client.import_image(src=maintenance['location'], repository=maintenance['name'], tag=maintenance['tag'])

    # key+cert.pem check
    if not os.path.exists(KEY_CERT_COMBINED_FILE):
        print '\nNo %s detected' % KEY_CERT_COMBINED_FILE
        configure_certificate()
    print 'Copying key+cert.pem into api and nginx bind mount locations'
    shutil.copy2(KEY_CERT_COMBINED_FILE, 'api')
    shutil.copy2(KEY_CERT_COMBINED_FILE, 'nginx')

    if not os.path.exists(ROOT_CERT_COMBINED_FILE):
        print '\nNo %s detected' % ROOT_CERT_COMBINED_FILE
        configure_CA()
    print 'Copying root cert file into nginx bind mount location'
    shutil.copy2(ROOT_CERT_FILE, 'nginx')
    if not os.path.exists(os.path.join('persistent', 'keys', 'client-engine-local-key+cert.pem')):
        print 'creating client certificate for a local engine.'
        create_client_cert('engine-local')
    if not os.path.exists(os.path.join('persistent', 'keys', 'client-reaper-key+cert.pem')):
        print 'creating a client certificate for a reaper.'
        create_client_cert('reaper')

    # generate config files
    generate_from_template(CONFIGJS_IN, CONFIGJS_OUT, nginx['fullName'], api['fullName'], mongo['fullName'])
    generate_from_template(FIG_IN, FIG_OUT, nginx['fullName'], api['fullName'], mongo['fullName'])

    stop(None)  # shutdown mongo clean between starts

    # pick appropriate nginx configuration
    if config.get('ssl_terminator'):
        sh.cp('nginx/nginx.sslterm.conf', 'nginx/nginx.conf')
    else:
        sh.cp('nginx/nginx.default.conf', 'nginx/nginx.conf')

    # Detect if cluster is new (has never been started before)
    newCluster = not os.path.isfile(os.path.join(config['storage']['mongo_path'], 'mongod.lock'))

    # Check configuration
    print "Checking configuration..."
    test(None)

    # start the containers
    print "Starting scitran..."
    fig_prefix = config.get('fig_prefix')
    fig = sh.Command("bin/fig")("-f", "containers/fig.yml", "-p", fig_prefix, "up", "-d", _out=process_output, _err=process_output)

    # add app, if requested by user
    # must bootstrap apps BEFORE data, to allow jobs to be created

    # Add new data if requested by user
    if newCluster:
        print '\nNew Instance Detected'
        print "\nAdding initial users, groups and drones from bootstrap.json"
        if not os.path.exists(BOOTSTRAP_OUT):
            print 'No %s detected' % BOOTSTRAP_OUT
            configure_json()
        bootstrap_db()

    if len(os.listdir(os.path.join(HERE, 'persistent', 'apps'))) == 0:
        print '\nNo Apps detected.'
        bootstrap_apps()

    if len(glob.glob(os.path.join(config['storage']['data_path'], '???'))) == 0:
        print '\nNo data detected.'
        bootstrap_data()

    # check the state of the instance, are all three containers running?
    # TODO: instead of checking that three containers are running try hitting the API with requests. HEAD /api
    current_status = instance_status()
    running = 0
    for k, v in current_status.iteritems():
        if current_status[k]['status'] != 'not running':
            running += 1
    if running == 3:
        print "\nCheck out your running site at https://" + config['domain']
        r = requests.get('https://%s/api' % (config['domain']), verify=False)
        if r.status_code != 200:
            print '\nSomething went wrong...'
        else:
            print "Scitran is running!"
    else:
        print '\nSomething went wrong...'


def stop(args):
    """Stop a running instance."""
    # only stop THIS configurations instance
    config = read_config(CONFIG_FILE)
    fig_prefix = config.get('fig_prefix')
    try:
        fig = sh.Command("bin/fig")("-f", "containers/fig.yml", "-p", fig_prefix, "stop", _out=process_output, _err=process_output)
    except sh.ErrorReturnCode as e:
        print e


def test(args):
    """Run various pre-launch tests"""
    config = read_config(CONFIG_FILE)
    fig_prefix = config.get('fig_prefix')
    # might be nice to separate the combined ca-ceritifcates.crt from this test...
    # this creates and tests the combined CA file.
    try:
        print 'Checking that previous mongod was shutdown gracefully...'
        mongodlock = os.path.join(config['storage']['mongo_path'], 'mongod.lock')
        if os.path.exists(mongodlock) and os.stat(mongodlock).st_size != 0:
            print '\nUnclean mongo shutdown detected. Removing stale lock file to allow mongo to recover from journal.'
            os.remove(mongodlock)
        print 'Checking nginx configuration...'
        sh.Command("bin/fig")("-f", "containers/fig.yml", "-p", fig_prefix, "run", "nginx", "/etc/nginx/run.sh", "-t", _out=process_output, _err=process_output)

    except sh.ErrorReturnCode as e:
        print
        print "Pre-launch checks failed; see above output for more."

        # For some reason, sh.ErrorReturnCode does not have a strongly-typed exit code variable.
        # This makes it mildly irritating to get a code out of an exception.
        # Oh well; reflection and string parsing it is then :/
        error = e.__class__.__name__
        underscore = error.rfind("_") + 1
        exit(int(error[underscore:]))

        # TODO: gather more information about the failure cause

    # fig run creates special containers with naming pattern of '/prefix_container_run_int', e.g. /local_nginx_run_1
    # delete these immediately to prevent accumulation of testing containers
    docker_client = docker.Client(base_url=config['docker_url'])
    for container in docker_client.containers(all=True):
        if ('/%s_nginx_run_1' % fig_prefix) in container['Names']:
            docker_client.stop(container=container['Id'])
            docker_client.remove_container(container=container['Id'], v=True)


def maintenance(args):
    """Print the command line to start a maintenance container."""
    config = read_config(CONFIG_FILE)
    fig_prefix = config.get('fig_prefix')
    print 'docker run -it --rm -e "PYTHONPATH=/service/code/data" --link %s_mongo_1:mongo -v %s/persistent/maintenance:/root -v %s/persistent:/persistent -v %s/code:/service/code %s /bin/bash' % (fig_prefix, HERE, HERE, HERE, getTarball('maintenance')['fullName'])


def info(args):
    print json.dumps(system_report(), indent=4, separators=(',', ': '))


def status(args):
    print json.dumps(instance_status(), indent=4, separators=(',', ': '))


def config(args):
    """Rerun, view, or remove the configuration."""
    if os.path.exists(CONFIG_FILE):
        print 'warning: config.json exists'
        if raw_input('Rerun config and obliterate old config.json? [y/N]: ').strip().lower() == 'y':
            write_config(generate_config(args.mode), CONFIG_FILE)
    else:
        write_config(generate_config(args.mode), CONFIG_FILE)
    if raw_input('Rerun bootstrap file configuration? [y/N]: ').strip().lower() == 'y':
        configure_json()
    if raw_input('Rerun bootstrap ssl certificate configuration? [y/N]: ').strip().lower() == 'y':
        configure_certificate()
    if raw_input('Rerun bootstrap certificate authority configuration? [y/N]: ').strip().lower() == 'y':
        configure_CA()

def add_drone(args):
    """Create a ssl certificate that is signed by our own certificate authority."""
    print 'creating client cert for drone %s' % args.drone_name
    if not os.path.exists(ROOT_CERT_COMBINED_FILE):
        print '\nA root certificate authority has not been created...creating...'
        create_self_certificate_authority()

    create_client_cert(args.drone_name)

# XXX: all of this engine stuff is likely to change.
# keep it grouped together until it settles down
def engine(args):
    """Control and configure this instance's engine."""
    config = read_config(CONFIG_FILE)
    scheme = 'https'
    # The engine goes through the "front door (ssl terminator)", in which case the outer nginx must be
    # configured to also use the instance created CA certificate.
    if config.get('ssl_terminator'):
        scheme = 'https'
    machine_api = '%s://%s:%s/api' % (scheme, config.get('domain'), config.get('machine_port'))
    if args.action == 'start':
        print 'code/engine/engine.py %s local persistent/keys/client-engine-local-key+cert.pem' % machine_api
    elif args.action == 'debug':
        print 'code/engine/engine.py %s local persistent/keys/client-engine-local-key+cert.pem --log_level debug' % machine_api

def purge(args):
    print '\nWARNING: PURGING'
    config = read_config(CONFIG_FILE)
    fig_prefix = config.get('fig_prefix')
    # removing images requires removing containers
    # removing containers requires instance to be stopped
    if args.containers or args.images or args.all:
        try:
            # --force disables fig's prompt to proceed with removal
            fig = sh.Command("bin/fig")("-f", "containers/fig.yml", "-p", fig_prefix, "rm", "--force", _out=process_output, _err=process_output)
        except sh.ErrorReturnCode as e:
            print e
    if args.images or args.all:
        print 'purging images...'
        c = docker.Client(config['docker_url'])
        for image in c.images():
            for repotag in image['RepoTags']:
                if repotag.startswith('scitran-'):
                    print 'purging image %s' % repotag
    if args.data or args.all:
        print 'purging data...'
        shutil.rmtree(config['storage']['data_path'])
    if args.db or args.all:
        print 'purging db...'
        shutil.rmtree(config['storage']['mongo_path'])


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
    start_parser.add_argument('--mode', help='configuration mode', choices=['default', 'advanced'], default='default')
    start_parser.set_defaults(func=start)

    # stop
    stop_parser = subparsers.add_parser(
        name='stop',
        help='stop',
        description='scitran stop',
        )
    stop_parser.set_defaults(func=stop)

    # test
    test_parser = subparsers.add_parser(
        name='test',
        help='test',
        description='scitran test',
        )
    test_parser.set_defaults(func=test)

    # system
    info_parser = subparsers.add_parser(
        name='info',
        help='Print information about this Scitran Instance.',
        description='./scitran.py info',
        )
    info_parser.set_defaults(func=info)

    # service
    maintenance_parser = subparsers.add_parser(
        name='maintenance',
        help='prints a shell command to launch a maintenance container. Can be backticked.',
        description='./scitran.py maintenance',
        )
    maintenance_parser.set_defaults(func=maintenance)

    # status
    status_parser = subparsers.add_parser(
        name='status',
        help='show status of instance',
        description='scitran status',
        )
    status_parser.set_defaults(func=status)

    # config
    config_parser = subparsers.add_parser(
        name='config',
        help='configure',
        description='scitran config',
        )
    config_parser.add_argument('--mode', help='configuration mode', choices=['default', 'advanced'], default='default')
    config_parser.set_defaults(func=config)

    # bootstrap
    bootstrap_parser = subparsers.add_parser(
            name='bootstrap',
            help='bootstrap',
            description='./scitran.py bootstrap',
            )
    bootstrap_parser.add_argument('--db', help='bootstrap the users, groups and drones in database', action='store_true')
    bootstrap_parser.add_argument('--apps', help='bootstrap an app', action='store_true')
    bootstrap_parser.add_argument('--data', help='bootstrap data', action='store_true')
    bootstrap_parser.add_argument('-f', '--force', help='dump existing target before bootstrapping.', action='store_true')
    bootstrap_parser.set_defaults(func=bootstrap)

    purge_parser = subparsers.add_parser(
        name='purge',
        help='remove scitan config, persistent data, containers and images. BRUTAL!',
        description='./scitran.py purge',
        )
    purge_parser.add_argument('--containers', help='purge containers', action='store_true') # harmless
    purge_parser.add_argument('--images', help='purge images', action='store_true')         # harmless
    purge_parser.add_argument('--data', help='purge data_path', action='store_true')        # destructive
    purge_parser.add_argument('--db', help='purge mongo_path', action='store_true')         # destructive
    purge_parser.add_argument('--all', help='purge containers, images, data_path, and mongo_path', action='store_true')     # destructive
    purge_parser.set_defaults(func=purge)

    add_drone_parser = subparsers.add_parser(
        name='add_drone',
        help='create signed client certificate for within this instance', # TODO better wording
        description='./scitran.py add_drone <drone_name>',
        )
    add_drone_parser.add_argument('drone_name', help='name of drone, ex. reaper, engine001')
    add_drone_parser.set_defaults(func=add_drone)

    engine_parser = subparsers.add_parser(
        name='engine',
        help='bootstrap, start and stop the engine',
        description='./scitran.py engine',
        )
    engine_parser.add_argument('action', help='control the local engine', choices=['start', 'status', 'stop', 'debug'])
    engine_parser.set_defaults(func=engine)

    # do it
    args = parser.parse_args()
    args.func(args)
