#!/usr/local/bin/python3
# -*- coding: utf-8 -*-

"""
backup-gitlab-repos-s3.py

Description:
    Backup Gitlab repositories to S3

Requirements:
    # https://python-gitlab.readthedocs.io/en/stable/
    python-gitlab module

Inputs:
    environment vars:
        GITLAB_URL
        GITLAB_USER
        GITLAB_TOKEN
        AWS_REGION
        AWS_PROFILE
        S3_BUCKET
"""

# Use try/except on external dependency modules
try:
    import gitlab
except ImportError:
    print("Module 'python-gitlab' not installed! Exiting script")
    quit(2)
# Built-in modules
import os
import sys
import time
import datetime
import re
import subprocess
import shlex
from time import strftime
from urllib.parse import urlparse

# Get name, path, basename of the this script
script_name = __file__
script_path = os.path.dirname(os.path.abspath(__file__))
script_basename = os.path.basename(script_name)

# Gitlab user/token used to clone repos
gitlab_url = os.environ.get('GITLAB_URL')
gitlab_user = os.environ.get('GITLAB_USER')
gitlab_token = os.environ.get('GITLAB_TOKEN')

# Local directory to clone repos to (must already exist)
local_clone_dir = script_path + "/gitlab-bkup-clone-repo"

# Make sure local_clone_dir exists before continuing
if not os.path.isdir(local_clone_dir):
    print("Directory for local cloning {} does not exist or unable to change dir to it!  Exiting script".format(local_clone_dir))
    quit(2)
else:
    print("Starting {}".format(script_name))

project_count = 0  # Count number of repos
repo_clone_count = 0  # Count number of repos cloned
successful_backup_count = 0  # Count number of successful backups to S3 
repository_url = []  # List containing all repo urls
repository_info = {}  # Dictionary containing repo info (repo url, path_with_namespace)
aws_region = os.environ.get('AWS_REGION')
aws_profile = os.environ.get('AWS_REGION')  # Can be left blank to use role
zip_file_name = ""
s3_upload_bucket = os.environ.get('S3_BUCKET')  # s3://bucket


def clone_repo(path_with_namespace, repo_url, clone_dir):
    # Git clone repo_url to directory clone_dir
    global gitlab_user, gitlab_token
    url_no_https = repo_url[8:]  # Remove https:// from repo
    os.chdir(clone_dir)
    try:
        os.makedirs(path_with_namespace)
    except FileExistsError as err:
        print("clone_repo: os.makedirs returned error: {}".format(err))
    except OSError as err:
        print("clone_repo: os.makedirs returned error: {}".format(err))
    os.chdir(path_with_namespace)
    git_cmd = "git clone https://{}:{}@{} .".format(gitlab_user, gitlab_token, url_no_https)
    exec_cmd = shlex.split(git_cmd)
    try:
        p = subprocess.Popen(exec_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as err:
        print("clone_repo: subprocess.Popen returned error: {}".format(err))
        return False
    pid = p.pid
    print("clone_repo: Running '{}', PID = {}".format(git_cmd, pid))
    cmdoutput, cmderr = p.communicate(input=None)  # Wait until subprocess git_cmd finishes and capture stdout/stderr
    retcode = p.returncode
    print("clone_repo: git command output: {}".format(cmderr))
    if retcode > 0:
        print("clone_repo: Error code '{}' returned from '{}', see log file '{}'".format(retcode, git_cmd, cmderr))
        return False
    return True


def zip_repo(path_with_namespace, repo_url, clone_dir):
    # Extract repo name from repo url and zip clone dir
    global zip_file_name
    repo_name = urlparse(repo_url)  # https://gitlab.com/repo.git
    repo_name = os.path.basename(repo_name.path)  # repo.git
    repo_name = repo_name.split(".")[0]  # rep
    zip_file_name = repo_name + ".zip"  # repo.zip
    os.chdir(clone_dir)
    zip_cmd = "zip -r {} {}".format(zip_file_name, path_with_namespace)  # zip -r repo.zip repo
    exec_cmd = shlex.split(zip_cmd)
    try:
        p = subprocess.Popen(exec_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as err:
        print("clone_repo: subprocess.Popen returned error: {}".format(err))
        return False
    pid = p.pid
    print("zip_repo: Running '{}', PID = {}".format(zip_cmd, pid))
    cmdoutput, cmderr = p.communicate(input=None)  # Wait until subprocess zip_cmd finishes and capture stdout/stderr
    retcode = p.returncode
    print("zip_repo: zip command output: {}".format(cmdoutput))
    if retcode > 0:
        print("zip_repo: Error code '{}' returned from '{}', see log file '{}'".format(retcode, zip_cmd, cmderr))
        return False
    return True


def s3_upload(file_name, path_with_namespace, bucket, aws_region):
    # Upload file to s3 bucket
    s3_cmd = "aws --region {} s3 cp {} {} --only-show-errors".format(aws_region, file_name, bucket + "/" + path_with_namespace + "/")  # zip -r repo.zip repo
    exec_cmd = shlex.split(s3_cmd)
    try:
        p = subprocess.Popen(exec_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as err:
        print("clone_repo: subprocess.Popen returned error: {}".format(err))
        return False
    pid = p.pid
    print("s3_upload: Running '{}', PID = {}".format(s3_cmd, pid))
    cmdoutput, cmderr = p.communicate(input=None)  # Wait until subprocess s3_cmd finishes and capture stdout/stderr
    retcode = p.returncode
    print("s3_upload: aws cli command output: {}".format(cmdoutput))
    if retcode > 0:
        print("s3_upload: Error code '{}' returned from '{}', see log file '{}'".format(retcode, s3_cmd, cmderr))
        return False
    return True

# Instantiate python-gitlab, private_token ensure's we're only getting our repos
gl = gitlab.Gitlab(gitlab_url, private_token="{}".format(gitlab_token))

# Loop over all private projects and add repository url to list
for project in gl.projects.list(visibility='private', all=True):
    repository_info[project.attributes['path_with_namespace']] = project.http_url_to_repo
    project_count += 1

# Exit if we didn't get any repos back, something is wrong if 0
if len(repository_info) > 0:
    print("Found {} Gitlab private repos to clone".format(project_count))
else:
    print("Found {} Gitlab private repos to clone.  Exiting script!".format(project_count))
    exit(2)

# Loop over all repository urls and git clone them, zip up clone dir, and upload to S3
if len(repository_info) > 0:
    for path_with_namespace, repo in repository_info.items():
        repo_clone_count += 1
        print("Cloning repo {} #{} of #{} into backup dir {}".format(path_with_namespace, repo_clone_count, project_count, local_clone_dir))
        if clone_repo(path_with_namespace, repo, local_clone_dir) is True:
            print("Successfully cloned repo {}".format(repo))
            print("Zipping cloned repo into zip file")
            if zip_repo(path_with_namespace, repo, local_clone_dir) is True:
                print("Successfully zipped repo {} #{} of #{}".format(path_with_namespace, repo_clone_count, project_count))
                print("Uploading repo zip file to S3")
                if s3_upload(local_clone_dir + "/" + zip_file_name, path_with_namespace, s3_upload_bucket, aws_region) is True:
                    print("Successfully uploaded repo {}.zip file #{} of #{} to S3".format(path_with_namespace, repo_clone_count, project_count))
                    successful_backup_count += 1
                    #break
                else:
                    print("Failed to upload zip to S3 for repo {}  See log file for error".format(repo))
                    #break
            else:
                print("Failed to zip repo {}  See log file for error".format(repo))
            #break
        else:
            print("Failed to clone repo {}  See log file for error".format(repo))
        #break
print("Done")
print("Backed up {} out of {} Gitlab repos to S3".format(successful_backup_count, project_count))
