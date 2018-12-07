#!/usr/bin/env python3

import fileinput
import json
import sys
from os import listdir
from os.path import isfile, join
import git
from dxf import DXF
import docker
import datetime
import io

analyzer_path = 'analyzers'
namespace = 'tooom'
username = 'tooom'
password = '****'
registry = 'registry-1.docker.io'
build_type = 'latest'  # or 'devel'
last_commit_label = 'git_commit'  # 'org.label-schema.vcs-ref'

docker_client = docker.from_env()


def auth(_dxf, response):
    _dxf.authenticate(username=username, password=password, response=response, actions='*')


def last_build_commit(repo, tag):
    try:
        dxf = DXF(host=registry, repo='%s/%s' % (namespace, repo), auth=auth)
        r = dxf._request('get', 'manifests/' + tag,
                         headers={'Accept': 'application/vnd.docker.distribution.manifest.v1+json'})
        metadata = json.loads(r.content.decode('utf-8'))
        return json.loads(metadata['history'][0]['v1Compatibility'])['config']['Labels'][last_commit_label]
    except:
        return None


def patch_requirements(filename):
    if isfile(filename):
        for req in fileinput.input(files=filename, inplace=1):
            if req.strip() == 'cortexutils':
                sys.stdout.write('git+https://github.com/TheHive-Project/cortexutils.git@feature/docker\n')
            else:
                sys.stdout.write(req)


def list_flavor(path):
    for flavor_filename in listdir(path):
        if isfile(join(path, flavor_filename)) and flavor_filename.endswith('.json'):
            with open(join(path, flavor_filename)) as flavor_file:
                flavor = json.load(flavor_file)
                yield flavor


def analyzer_is_updated(flavor, analyzer_name):
    last_commit = last_build_commit(flavor['name'].lower(), build_type)
    if last_commit is None:
        return True
    repo = git.Repo('.')
    head = repo.head.commit
    for change in head.diff(other=last_commit):
        if change.a_path.startswith(join(analyzer_path, analyzer_name)) or \
                change.b_path.startswith(join(analyzer_path, analyzer_name)):
            return True
    return False


def git_commit_sha(path='.'):
    return git.Repo(path).head.commit.hexsha


def build_docker(analyzer_name, flavor):
    dockerfile = """  
FROM python:3

WORKDIR /analyzer
COPY . {analyzer_name}
RUN pip install --no-cache-dir -r {analyzer_name}/requirements.txt
CMD {command}
""".format(analyzer_name=analyzer_name, command=flavor['command'])

    docker_client.images.build(
        path=join(analyzer_path, analyzer_name),
        fileobj=io.BytesIO(str.encode(dockerfile)),
        pull=True,
        labels={
            'org.label-schema.build-date': datetime.datetime.now().isoformat('T') + 'Z',
            'org.label-schema.name': analyzer_name,
            'org.label-schema.description': flavor['description'],
            'org.label-schema.url': 'https://thehive-project.org',
            'org.label-schema.vcs-url': 'https://github.com/TheHive-Project/Cortex-Analyzers',
            'org.label-schema.vcs-ref': git_commit_sha(),
            'org.label-schema.vendor': 'TheHive Project',
            'org.label-schema.version': flavor['version']
        },
        tag='%s/%s' % (namespace, flavor['name'].lower()))


def build_analyzers():
    for analyzer_name in listdir(analyzer_path):
        updated_flavors = [flavor
                           for flavor in list_flavor(join(analyzer_path, analyzer_name))
                           if analyzer_is_updated(flavor, analyzer_name)]
        patch_requirements(join(analyzer_name, analyzer_name, "requirements.txt"))
        for flavor in updated_flavors:
            print("analyzer %s has been updated" % flavor['name'])
            build_docker(analyzer_name, flavor)


if __name__ == '__main__':
    build_analyzers()
