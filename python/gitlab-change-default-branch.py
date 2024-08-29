#!/usr/bin/env python3

# This script takes two arguments and loops over projects in a YAML file setting the default branch
#   Input arg1: gitlab url
#   Input arg2: YAML input file
#   Input environment var(GL_TOKEN): Gitlab private token

import gitlab
import argparse
import os
import yaml

# Check Python version
req_version = (3, 9)
cur_version = os.sys.version_info

if not cur_version >= req_version:
    print('Your Python interpreter is too old. Please consider upgrading to at least 3.9')
    exit(2)

script_name = os.path.basename(__file__)

# Get cli arguments
parser = argparse.ArgumentParser(description="Change default branch on all Gitlab projects in a yaml file")
parser.add_argument("gitlab_url", help="Gitlab URL", type=str)
parser.add_argument("ymlfile", help="YAML file name as input", type=str)
args = parser.parse_args()
gitlab_url = args.gitlab_url
yml_input_file = args.ymlfile
gitlab_token = os.environ.get('GL_TOKEN')

# Confirm file exists
if not os.path.isfile(yml_input_file):
    print("The input csv file doesn't exist!  Exiting script")
    exit(2)

# Check if we got Gitlab private token from env var
if not gitlab_token:
    print("GL_TOKEN environment variable not set!  Exiting script")
    exit(2)

# Show script supplied arguments
print(f'Starting {script_name} script')
print(f'Gitlab URL: {gitlab_url}')
print(f'YAML Input File Name: {yml_input_file}')

def change_default_branch(yml_repo, yml_group_id, yml_project_id, yml_default_branch):
    print(f'Processing {yml_repo} repo...')
    global total_project_count
    global total_projects_changed
    total_project_count += 1
    gl = gitlab.Gitlab(gitlab_url, private_token=gitlab_token)
    try:
        group = gl.groups.get(yml_group_id)
    except Exception as error:
        print(f'Error: {error}')
        exit(2)

    try:
        projects = group.projects.list(include_subgroups=True, all=True)
    except Exception as error:
        print(f'Error: {error}')
        exit(2)

    for project in projects:
        if project.id == yml_project_id:
            print('  Found target project, checking default branch...')
            if project.default_branch == yml_default_branch:
                print('  Default branch already set')
            else:
                print(f"  Changing default branch to '{yml_default_branch}'")
                p = gl.projects.get(str(project.id), lazy=True)
                p.default_branch = yml_default_branch
                try:
                    p.save()
                    total_projects_changed += 1
                except Exception as error:
                    # This error '403: insufficient_scope' means the personal gitlab token does not have api write access
                    print(f'Error: {error}')
                    exit(2)

# Set counters for stats
repo_count = 0
total_project_count = 0
total_projects_changed = 0

# Open and read in the yaml input file
repos = {}
try:
    with open(yml_input_file) as f:
        repos = yaml.safe_load(f)
except Exception as error:
    print(f'Error: {error}')
    exit(2)

# Loop over the repos we got from the yaml file and update the default_branch
for key, value in repos.items():
    print('Starting loop over yaml file to change default branch for each project')
    repo_count += 1
    try:
        yml_group_id = value['group-id']
        yml_project_id = value['project-id']
        yml_default_branch = value['default-branch']
    except KeyError as key_error:
        print(f'Error: key {key_error} in yaml file  does not exist!  Exiting script')
        exit(2)
    except Exception as error:
        print(f'Error: {error}')
        exit(2)
    change_default_branch(key,yml_group_id, yml_project_id, yml_default_branch)

# Done, exit with stats
print('')
print(f'Processed {repo_count - 1} repos in yml')
print(f'Processed {total_project_count} projects')
print(f'Changed {total_projects_changed} projects')