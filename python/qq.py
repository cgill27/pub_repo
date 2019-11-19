#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
qq.py

Description:
This script is helpful for connecting to AWS EC2 instances if you do not
    know the instance ip address, name, ssh key etc
Run script by itself to return a list of EC2 instances in the
    'default' aws cli profile account or it uses this instance's IAM role for account access
You can return EC2 instances from other accounts by specifying the account argument
    (provided the profiles are setup your local ~/.aws/credentials file
You can create a yaml file 'qq-defaults.yaml' that contains some default settings
    like the vpc id, so when you run the script you only return hosts in the vpc id(s) specified,
    or region to use.
    The vpc id can be a comma separated list to return hosts for multiple vpc's.
    *Note: If there is a vpc id specified in 'qq-defaults.yaml' any name searches, environment
        searches, or vpc id searches will only return results for the vpc id(s) specified in 'qq-defaults.yaml'

*Note: If you need to ssh into any EC2 instance with a specific user you can add an EC2 Tag to the
    instance and this qq script will ssh into that instance with that userid (example):
    Tag:
      SSHUser   ubuntu

Python external requirements:  (see qq_requirements.txt file)
External script requirements:  (none)

If you need to create a requirements file manually, put the below in file (qq_requirements.txt):
awscli
argparse
pyfiglet
boto3
termcolor
requests
pyyaml

To install qq.py requirements execute: sudo pip install --upgrade -r qq_requirements.txt

"""

# Wrap modules that may not be installed by default in try's
try:
    import argparse
except ImportError:
    print "Module 'argparse' not installed! Exiting script"
    quit(2)
try:
    from pyfiglet import Figlet
    figlet_installed = True
except ImportError:
    figlet_installed = False
try:  # Try to use the latest version of Boto3
    import boto3
    from botocore.exceptions import *
except ImportError:
    print "Module 'boto3' not installed! Exiting script"
    quit(2)
try:
    from termcolor import colored
except ImportError:
    print "Module 'termcolor' not installed! Exiting script"
    quit(2)
try:
    import yaml
except ImportError:
    print "Module 'pyyaml' not installed!  Pip install or download and install from http://pyyaml.org/"
    quit(2)
try:
    import requests
except ImportError:
    print "Module 'requests' not installed! Exiting script"
    quit(2)
# Modules below are usually built-in and do not need to be installed
import os
import sys
import logging
import time
import datetime
import re
import subprocess
import shlex

# Check Python version and exit if not at least 2.7
req_version = (2, 7)
cur_version = os.sys.version_info

if not cur_version >= req_version:
    print "Your Python interpreter is too old. Please consider upgrading to at least Python 2.7"
    quit(2)

# If False then no logs are created, only the status at the end is displayed
debug = True

# If True logs are also printed to screen
print_log = False

# Get name, path, version of this script
script_name = __file__
script_path = os.path.dirname(os.path.abspath(__file__))
script_basename = os.path.basename(script_name)

# Get Python binary executable path (for calling other python scripts later)
python_bin = sys.executable


def printhelp():
    # Show help options
    if figlet_installed is True:
        f = Figlet(font='slant')
        print f.renderText(script_name)
    print " "
    print "This script is helpful for connecting to AWS EC2 instances if you do not"
    print "  know the instance ip address, name, ssh key etc"
    print " "
    print "If you do know the ip address you want to ssh to, see Usage1 below"
    print " "
    print "Running with no cli arguments brings up a list of running instances for your configured"
    print "  aws cli profile or IAM instance role"
    print " "
    print "Example usages (Do not combine -e -n -k -i -v -g, choose one):"
    print "Usage0: %s" % script_name
    print "Usage1: %s <ip address>" % script_name
    print "Usage2: %s -e <Environment tag regex search term>" % script_name
    print "Usage3: %s -n <Name tag regex search term>" % script_name
    print "Usage4: %s -k" % script_name
    print "Usage5: %s -i <ip address>" % script_name
    print "Usage6: %s -v <vpc id>" % script_name
    print "Usage7: %s -g <group name>" % script_name
    print "Usage8: %s -s" % script_name
    print "Usage9: %s -e <Environment tag regex search term> -r <region>" % script_name
    print "Usage10: %s -e <Environment tag regex search term> -p <aws profile name>" % script_name
    print "Usage11: %s -p <aws profile name>" % script_name
    print " "
    print "Optional args:"
    print "-e | --environment      Specify an Environment tag to regex search for"
    print "-n | --name             Specify a Name tag to regex search for"
    print "-k | --key              Show all instances that match ssh keys on this host"
    print "-i | --ip               Connect to host with this ip address (i.e. search only for ssh key to use and connect)"
    print "-v | --vpcid            Show all instances in VPC id"
    print "-g | --groupname        Show all instances associated to group name in 'qq-groups.yaml' file"
    print "-s | --showgroups       Show all group names in group file 'qq-groups.yaml' file"
    print "-p | --profile          AWS profile name (generated by 'aws configure'), IAM role used if profile not specified"
    print "-r | --region           Specify AWS region (default: us-east-1)"
    print " "
    print "-d | --debuglevel       Level of logging (debug, info, warning, error, critical)"
    print "-l | --debuglog         Log file to log to (full path)"
    print "Note: if 'TIMESTAMP' is in debugLog file name, it will be substituted with a timestamp"
    print "Note2: 'debug = True' must be set in script for logging to happen"
    print " "
    print "Help: %s -h" % script_name
    print " "
    quit(1)


# Parse cli options
parser = argparse.ArgumentParser(description="This script is helpful for connecting to AWS EC2 instances, returns a list of instances in the account")
#   Optional args
parser.add_argument("-e", "--environment", type=str, help="Specify an Environment tag to search for")
parser.add_argument("-n", "--name", type=str, help="Specify a Name tag to search for")
parser.add_argument("-k", "--key", action='store_true', help="Show all instances that match ssh keys on this host")
parser.add_argument("-i", "--ip", type=str, help="Connect to host with this ip address (i.e. search only for ssh key to use and connect)")
parser.add_argument("-v", "--vpcid", type=str, help="Show all instances in VPC id")
parser.add_argument("-g", "--groupname", type=str, help="Show all instances associated to group name in 'qq-groups.yaml' file")
parser.add_argument("-s", "--showgroups", action='store_true', help="Show all group names in group file 'qq-groups.yaml' file")
parser.add_argument("-p", "--profile", type=str, help="AWS profile name (generated by 'aws configure'), IAM role used if profile not specified")
parser.add_argument("-r", "--region", type=str, help="Specify AWS region (default: us-east-1)")
parser.add_argument("-d", "--debugLevel", type=str, choices=["debug", "info", "warning", "error", "critical"], help="Set debug level")
parser.add_argument("-l", "--debugLog", type=str, help="Debug log file name if debugLevel is set")

# Check for help argument and print help
if "-h" in sys.argv or "--help" in sys.argv or "/h" in sys.argv or "/?" in sys.argv:
    printhelp()

# Check if the first given argument is an ip address, if it is then skip argument parsing and ssh to it
parse_args = True
search_ip = False
for x in sys.argv:
    if x.startswith(script_basename):
        continue
    if "." in x:
        string_argv = str(x)
        if "." in string_argv:
            if ".log" in string_argv:
                continue
            ipaddress = string_argv.split(".")
            if len(ipaddress) != 4:
                print "Invalid ip address in first argument (there's not 4 octets): %s" % string_argv
                quit(2)
            for i in ipaddress:
                if not i.isdigit():
                    print "Invalid ip address in first argument (not all digits): %s" % string_argv
                    quit(2)
                i = int(i)
                if i < 0 or i > 255:
                    print "Invalid ip address in first argument (digit not between 0-255): %s" % string_argv
                    quit(2)
            ip_search = string_argv
            search_ip = True
            parse_args = False
        else:
            search_ip = False
            parse_args = True
            ip_search = ""


if parse_args is True:
    args = parser.parse_args()  # Parse cli arguments

    # Optional arg, get aws Environment tag search string
    search_environment = False
    if hasattr(args, "environment") and args.environment is not None:
        env_search = args.environment
        env_search = env_search.strip()
        search_environment = True
    else:
        env_search = ''

    # Optional arg, get aws Name tag search string
    search_name = False
    if hasattr(args, "name") and args.name is not None:
        name_search = args.name
        name_search = name_search.strip()
        search_name = True
    else:
        name_search = ''

    # Optional arg, do ssh Key search
    key_search = False
    if hasattr(args, "key") and args.key is not None:
        if args.key is True:
            key_search = True
        else:
            key_search = False
    else:
        key_search = False

    # Optional arg, get ip address search string
    if search_ip is False:
        if hasattr(args, "ip") and args.ip is not None:
            ip_search = args.ip
            ip_search = ip_search.strip()
            search_ip = True
        else:
            ip_search = ''
    else:
        ip_search = ipaddress

    # Optional arg, get vpcid search string
    search_vpc = False
    if hasattr(args, "vpcid") and args.vpcid is not None:
        vpc_search = args.vpcid
        vpc_search = vpc_search.strip()
        vpc_search = list(vpc_search.split(','))  # Turn the vpc id(s) setting into a list to be passed to boto3 ec2 filter
        search_vpc = True
    else:
        vpc_search = ''

    # Optional arg, get groupname search string
    #   Open yaml file 'qq-groups.yaml' and find grouping of ip's under group name provided
    search_group = False
    group_yaml_filename = "qq-groups.yaml"  # Default group file name (stored in same directory as qq)
    if hasattr(args, "groupname") and args.groupname is not None:
        group_name_search = args.groupname
        group_name_search = group_name_search.strip()
        search_group = True
    else:
        group_name_search = ''

    # Optional arg, show all group names in default yaml group file 'qq-groups.yaml'
    list_groups = False
    if hasattr(args, "showgroups") and args.showgroups is not None:
        if args.showgroups is True:
            list_groups = True
        else:
            list_groups = False
    else:
        list_groups = False

    # Optional arg, get aws profile to connect with or use 'default' in aws credentials file ~/.aws/credentials, IAM role used if not specified
    profile_region_set = False
    if hasattr(args, "profile") and args.profile is not None:
        aws_profile = args.profile
        aws_profile = aws_profile.strip()
        profile_region_set = True
    else:
        aws_profile = ""

    # Optional arg, get aws region to connect with or use 'us-east-1' as default
    #   If profile_region_set and below region_set are False then region will be determined
    #   by HTTP GET of EC2 instance metadata
    region_set = False
    if hasattr(args, "region") and args.region is not None:
        aws_region = args.region
        aws_region = aws_region.strip()
        region_set = True
    else:
        aws_region = "us-east-1"

    # Optional arg, setup logging if specified at cli
    debuglevelSpecified = False
    if hasattr(args, "debugLevel") and args.debugLevel is not None:
        debugLevel = args.debugLevel
        debugLevel = debugLevel.strip()
        debuglevelSpecified = True
        if hasattr(args, "debugLog"):
            debugLog = args.debugLog
            debugLog = str(debugLog)
            debugLog = debugLog.strip()
            if debugLog.find(
                    "TIMESTAMP") > 0:  # If the word 'TIMESTAMP' is found in debugLog argument, replace with debugLog_suffix
                # https://docs.python.org/2/library/time.html
                debugLog_suffix = datetime.now().strftime(
                    "%Y%m%d%H%M%S")  # 20130101235959  year month day hour minute second
                debugLog = debugLog.replace("TIMESTAMP", debugLog_suffix)
            debugLogDir = os.path.dirname(os.path.abspath(debugLog))
            if not os.path.isdir(debugLogDir):
                print "Option 'debugLog' needs to specify full path to a log file!  Exiting script"
                printhelp()
        else:
            print "If specifying debugLevel, also specify debugLog!  Exiting script"
            printhelp()
        debugLevelOptions = ["debug", "info", "warning", "error", "critical"]
        if debugLevel in debugLevelOptions:
            if debugLevel == "debug":
                logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog,
                                    filemode='a')
            elif debugLevel == "info":
                logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog,
                                    filemode='a')
            elif debugLevel == "warning":
                logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(message)s',
                                    filename=debugLog, filemode='a')
            elif debugLevel == "error":
                logging.basicConfig(level=logging.ERROR, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog,
                                    filemode='a')
            elif debugLevel == "critical":
                logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s %(levelname)s %(message)s',
                                    filename=debugLog, filemode='a')
        else:
            print "Option 'debugLevel' needs to be one of [debug, info, warning, error, critical]!  Exiting script"
            printhelp()
        loggingEnabled = True
    else:
        loggingEnabled = False
        debugLevel = ""
        debugLog = ""
else:  # Set defaults for not parsing arguments
    profile_region_set = False
    region_set = False
    loggingEnabled = False
    debugLevel = ""
    debugLog = ""
    env_search = ""
    name_search = ""
    key_search = False
    vpc_search = ""
    group_name_search = ""
    search_group = False
    aws_profile = ""
    list_groups = False
    search_vpc = False
    search_name = False
    search_environment = False
    debuglevelSpecified = False


def logger(log, level="debug"):
    """ Log to debugLog if logging enabled """
    if loggingEnabled and debug:  # Only log if debugging set to True (top of this script) and debug level/log are set at the cli
        if print_log is True:
            print level + ": %s" % log
        if level == "debug":
            logging.debug(log)
        if level == "info":
            logging.info(log)
        if level == "warning":
            logging.warning(log)
        if level == "error":
            logging.error(log)
        if level == "critical":
            logging.critical(log)
        return True
    else:
        return False


def get_ec2_metadata():
    # Get region and other meta data from HTTP GET to EC2 meta data url if no region cli option specified
    #   *Note: This url will timeout on non-EC2 instances so you will need to specify the --region cli option
    global aws_region, aws_az, my_instanceid, aws_account, bastion_vpc_id
    try:
        r = requests.get("http://169.254.169.254/latest/dynamic/instance-identity/document", timeout=3)
    except requests.exceptions.RequestException as err:
        logger("HTTP GET region failed! Error: %s  Exiting script (Use --region argument to manually specify region)" % err, "critical")
        printstring = "HTTP GET region failed! Error: %s  Exiting script (Use --region argument to manually specify region)" % err
        print("{0}".format(colored(printstring, 'red')))
        quit(2)
    if r.status_code == 200:
        try:
            response_json = r.json()
        except ValueError as err:
            logger("Decoding json metadata get failed! Error: %s  Exiting script" % err, "critical")
            printstring = "Decoding json metadata get failed! Error: %s  Exiting script" % err
            print("{0}".format(colored(printstring, 'red')))
            quit(2)
        aws_region = response_json.get('region')
        aws_az = response_json.get('availabilityZone')
        my_instanceid = response_json.get('instanceId')
        aws_account = response_json.get('accountId')
    else:
        logger("HTTP GET region failed!  HTTP status code: %s  Exiting script (Use --region argument to manually specify region)" % r.status_code, "critical")
        printstring = "HTTP GET region failed!  HTTP status code: %s  Exiting script (Use --region argument to manually specify region)" % r.status_code
        print("{0}".format(colored(printstring, 'red')))
        quit(2)
    try:
        # Get network interface mac address - needed to get vpc id
        r = requests.get("http://169.254.169.254/latest/meta-data/network/interfaces/macs/", timeout=3)
    except requests.exceptions.RequestException as err:
        logger("HTTP GET mac address failed! Error: %s  Exiting script (Use --region argument to manually specify region)" % err, "warning")
        printstring = "HTTP GET mac address failed! Error: %s  Exiting script (Use --region argument to manually specify region)" % err
        print("{0}".format(colored(printstring, 'red')))
    if r.status_code == 200:
        mac_address = str(r.text)
        mac_address = mac_address.strip("/")
        try:
            # Get vpc id
            r = requests.get("http://169.254.169.254/latest/meta-data/network/interfaces/macs/%s/vpc-id" % mac_address, timeout=3)
        except requests.exceptions.RequestException as err:
            logger("HTTP GET vpc id failed! Error: %s" % err, "warning")
            printstring = "HTTP GET vpc id failed! Error: %s" % err
            print("{0}".format(colored(printstring, 'red')))
        if r.status_code == 200:
            bastion_vpc_id = str(r.text)
        else:
            logger("HTTP GET vpc id failed! HTTP status code: %s" % r.status_code, "warning")
            printstring = "HTTP GET vpc id failed! HTTP status code: %s" % r.status_code
            print("{0}".format(colored(printstring, 'red')))
    else:
        logger("HTTP GET mac address failed! HTTP status code: %s" % r.status_code, "warning")
        printstring = "HTTP GET mac address failed! HTTP status code: %s" % r.status_code
        print("{0}".format(colored(printstring, 'red')))
    return aws_region, aws_az, my_instanceid, aws_account, bastion_vpc_id


aws_region = "us-east-1"  # Set default region
aws_az = ""
my_instanceid = ""
aws_account = ""
bastion_vpc_id = ""
# Get EC2 metadata for instance we're running on
if profile_region_set is False and region_set is False and parse_args is True:
    aws_region, aws_az, my_instanceid, aws_account, bastion_vpc_id = get_ec2_metadata()


# Start the log file if logging specified
logger(" ", "info")
script_start_time = time.time()
time_string = datetime.datetime.fromtimestamp(script_start_time)
time_string = time_string.strftime('%Y-%m-%d %H:%M:%S')
logger("--+** Starting '%s' script at %s **+--" % (script_name, time_string), "info")
logger("script_path = '%s'" % script_path, "debug")
if debugLevel is not "":
    logger("debugLevel = '%s'" % debugLevel, "debug")
if debugLog is not "":
    logger("debugLog = '%s'" % debugLog, "debug")
logger("AWS environment tag search = '%s'" % env_search, "debug")
logger("AWS name tag search = '%s'" % name_search, "debug")
if key_search is True:
    logger("AWS key search = True", "debug")
else:
    logger("AWS key search = False", "debug")
logger("AWS ip search = '%s'" % ip_search, "debug")
logger("AWS vpcid search = '%s'" % vpc_search, "debug")
logger("Groupname search = '%s'" % group_name_search, "debug")
if search_group is True:
    logger("Group yaml file = '%s'" % script_path + "/" + group_yaml_filename, "debug")
logger("AWS profile specified = '%s'" % aws_profile, "debug")
if profile_region_set is False and region_set is False:
    logger("AWS region (from HTTP GET metadata url) = '%s'" % aws_region, "debug")
    logger("AWS availabilityZone (from HTTP GET metadata url) = '%s'" % aws_az, "debug")
    logger("AWS account (from HTTP GET metadata url) = '%s'" % aws_account, "debug")
    logger("AWS instanceId (from HTTP GET metadata url) = '%s'" % my_instanceid, "debug")
    logger("Bastion vpc id (from HTTP GET metadata url) = '%s'" % bastion_vpc_id, "debug")
else:
    logger("AWS region specified (default) = '%s'" % aws_region, "debug")


def sshtohost(key, ip, user):
    # Run 'ssh -i ~/.ssh/<key> <user>@<ip>' to ssh into host
    cmd = "ssh -4 -i %s -o ConnectTimeout=15 -o ServerAliveInterval=15 -o StrictHostKeyChecking=no %s@%s" % (key, user, ip)
    exec_cmd = shlex.split(cmd)
    global debuglevelSpecified
    if debuglevelSpecified is True:
        try:
            p = subprocess.Popen(exec_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        except OSError as err:
            logger("sshtohost: subprocess.Popen returned error: %s" % err, "critical")
            print "sshtohost: subprocess.Popen returned error: %s" % err
            return False
    else:
        try:
            p = subprocess.Popen(exec_cmd)
        except OSError as err:
            print "sshtohost: subprocess.Popen returned error: %s" % err
            return False
    pid = p.pid
    logger("sshtohost: Running '%s', PID = %s" % (cmd, pid), "info")
    cmdoutput, cmderr = p.communicate()  # Wait until subprocess cmd finishes and capture stdout/stderr
    retcode = p.returncode
    logger("sshtohost: ssh command output: %s" % cmdoutput, "debug")
    if retcode > 0:
        logger("sshtohost: Error code '%s' returned from '%s', see log file '%s'" % (retcode, cmd, cmderr), "critical")
        return False
    return True


# Yaml file for script default settings (stored in same directory as this script)
#   In this defaults file we set things like the vpcid if we want to specify a specific vpc,
#     or region to set a specific region without auto detecting it
#   *Note: All returned hosts will be for the vpc id(s) specified in this file
defaults_yaml_filename = "qq-defaults.yaml"
logger("Defaults yaml file = '%s'" % defaults_yaml_filename, "debug")

# Read in script defaults yaml file if present and get script default settings (like vpc id(s))
#   *Note: These settings will override any cli options specified
defaults_yaml_fileexists = True
default_vpc = False
default_region = False
if os.path.exists(script_path + "/" + defaults_yaml_filename) and os.path.isfile(script_path + "/" + defaults_yaml_filename):
    try:
        stream = file(script_path + "/" + defaults_yaml_filename, 'r')
        setting_in_file = yaml.safe_load(stream)
    except:  # Default settings yaml file does not exist or is unreadable!
        logger("Error reading defaults yaml file '%s'! Exiting script" % script_path + "/" + defaults_yaml_filename, "debug")
        printstring = "Error reading defaults yaml file '%s'! Exiting script" % (script_path + "/" + defaults_yaml_filename)
        print("{0}".format(colored(printstring, 'red')))
        quit(2)
    for k, setting_list in setting_in_file.iteritems():
        settings_section = k
        if settings_section == "Settings":
            try:
                vpc_search = setting_list['vpcid']
                default_vpc = True
            except KeyError as err:
                logger("Could not find 'vpcid' in Settings section of: %s" % defaults_yaml_filename, "debug")
                #print "Could not find 'vpcid' in Settings section of: %s" % defaults_yaml_filename
                #quit(2)
            try:
                aws_region = setting_list['region']
                default_region = True
            except KeyError as err:
                logger("Could not find 'region' in Settings section of: %s" % defaults_yaml_filename, "debug")
                #print "Could not find 'region' in Settings section of: %s" % defaults_yaml_filename
                #quit(2)
        else:
            logger("No 'Settings' section in defaults yaml file! Exiting script", "debug")
            printstring = "No 'Settings' section in defaults yaml file! Exiting script"
            print("{0}".format(colored(printstring, 'red')))
            quit(2)
        if default_vpc is True:
            vpc_search = list(vpc_search.split(','))  # Turn the vpc id(s) setting into a list to be passed to boto3 ec2 filter
else:
    logger("Defaults yaml file '%s' does not exist, not setting any script defaults" % script_path + "/" + defaults_yaml_filename, "info")
    defaults_yaml_fileexists = False


# Create AWS api session with either provided profile account or no account (IAM role used)
try:
    if aws_profile is not "":
        session = boto3.Session(profile_name=aws_profile)
    else:
        session = boto3.Session()
except ProfileNotFound as err:
    logger("AWS Profile '%s' not found! Error: %s   Exiting script" % (aws_profile, err), "critical")
    printstring = "AWS Profile '%s' not found! Error: %s   Exiting script" % (aws_profile, err)
    print("{0}".format(colored(printstring, 'red')))
    quit(2)


# Create AWS Boto3 client
try:
    ec2 = boto3.client("ec2", region_name=aws_region)
except EndpointConnectionError as err:
    logger("Unable to connect to AWS EC2 api in specified region '%s'! Error: %s   Exiting script" % (aws_region, err), "critical")
    printstring = "Unable to connect to AWS EC2 api in specified region '%s'! Error: %s   Exiting script" % (aws_region, err)
    print("{0}".format(colored(printstring, 'red')))
    quit(2)


# Issue describe instances query with filters to get a list of ec2 instances
if default_vpc is True:
    # Using vpc id(s) from qq-defaults file
    filters = [{'Name': 'vpc-id', 'Values': vpc_search}]  # The 'Values' needs to be a list passed in
    try:
        ec2_instances = ec2.describe_instances(Filters=filters)
    except ParamValidationError as err:
        logger("Boto3 ec2 describe_instances filter parameter error  Error: %s   Exiting script" % err, "critical")
        printstring = "Boto3 ec2 describe_instances filter parameter error  Error: %s   Exiting script" % err
        print("{0}".format(colored(printstring, 'red')))
        quit(2)
    except ClientError as err:
        logger("Boto3 ec2 describe_instances invalid parameter  Error: %s   Exiting script" % err, "critical")
        printstring = "Boto3 ec2 describe_instances invalid parameter  Error: %s   Exiting script" % err
        print("{0}".format(colored(printstring, 'red')))
        quit(2)
    boto3_num_hosts = len(ec2_instances['Reservations'])
    if boto3_num_hosts is 0:
        logger("VpcId(s) specified in qq-defaults.yaml but boto3 returned no hosts in vpc!", "info")
        print("{0}".format(colored("VpcId(s) specified in qq-defaults.yaml but boto3 returned no hosts in vpc!", "red")))
        quit(0)
    else:
        logger("VpcId(s) specified in qq-defaults.yaml and boto3 returned %d hosts in vpc" % boto3_num_hosts, "info")
        # print("{0}".format(colored("VpcId(s) specified in qq-defaults.yaml and boto3 returned %d hosts in vpc" % boto3_num_hosts, "red")))
else:
    try:
        ec2_instances = ec2.describe_instances()
    except ClientError as err:
        logger("Boto3 ec2 describe_instances client error: %s   Exiting script" % err, "critical")
        printstring = "Boto3 ec2 describe_instances client error: %s   Exiting script" % err
        print("{0}".format(colored(printstring, 'red')))
        quit(2)
    boto3_num_hosts = len(ec2_instances['Reservations'])
    if boto3_num_hosts is 0:
        logger("Boto3 returned no hosts!", "info")
        print("{0}".format(colored("Boto3 returned no hosts!", "red")))
        quit(0)
    else:
        logger("Boto3 returned %d hosts" % boto3_num_hosts, "info")
        # print "Boto3 returned %d hosts" % boto3_num_hosts

# Show an index number for each instance returned, we choose this number to ssh into a particular host
index_num = 0

# Dictionary containing list of returned hosts
returned_hosts = {}

# Vars and EC2 instance tags needed to ssh into host
tagname = ""  # Tag: Name
tagenvironment = ""  # Tag: Environment
instance_sshkey = ""  # Key pair name
tagsshuser = ""  # Tag: SSHUser (custom tag that specifies what ssh user to use)

# Loop over the ssh keys installed on this host in this users .ssh directory and store in a List
#   If no <key pair name>.pem files are found then exit qq, we can't ssh to any hosts anyway
ssh_keys_list = []
ssh_keys_list_exclude = ["authorized_keys", "known_hosts"]
for dirpath, dirnames, filenames in os.walk(os.path.expanduser('~/.ssh')):
    for f in filenames:
        if f in ssh_keys_list_exclude:
            continue
        try:
            filename, extension = f.split(".")
        except ValueError:  # File did not contain a period or contained multiple periods
            logger("Ssh keys os.walk found file either with no period or multiple periods (so unable to add key to list): %s" % f, "debug")
            continue
        filename = filename.upper()  # Store key name in uppercase, that's how they are stored in AWS
        ssh_keys_list.append(filename)
if len(ssh_keys_list) == 0:  # No ssh keys were found so we'll exit
    logger("There are no ssh keys found in ~/.ssh so cannot ssh! Exiting script", "warning")
    printstring = "There are no ssh keys found in ~/.ssh so cannot ssh! Exiting script"
    print("{0}".format(colored(printstring, 'red')))
    quit(1)

# Show group names in a default group file with -s cli option and then exit
if list_groups is True:
    if os.path.exists(script_path + "/" + group_yaml_filename) and os.path.isfile(script_path + "/" + group_yaml_filename):
        try:
            stream = file(script_path + "/" + group_yaml_filename, 'r')
            group_in_file = yaml.safe_load(stream)
        except:  # Default group file does not exist!
            logger("Error reading group file '%s'! Exiting script" % script_path + "/" + group_yaml_filename, "debug")
            printstring = "Error reading group file '%s'! Exiting script" % (script_path + "/" + group_yaml_filename)
            print("{0}".format(colored(printstring, 'red')))
            quit(2)
        for k, group_search_list in group_in_file.iteritems():
            group_name = k
            group_description = group_search_list['GroupDescription']
            print("Group Name: {0}   ".format(colored(k, 'green')) + "Group Description: {0}   ".format(colored(group_description, 'green')))
    else:
        logger("Group yaml file '%s' does not exist, unable to use -s switch! Exiting script" % script_path + "/" + group_yaml_filename, "critical")
        printstring = "Group yaml file '%s' does not exist, unable to use -s switch! Exiting script" % (script_path + "/" + group_yaml_filename)
        print("{0}".format(colored(printstring, 'red')))
        quit(1)
    quit(0)

# Show group of hosts to ssh to from -g option
#   Read in a group of ssh hosts from a yaml file
#   Display those hosts that match group name specified with -g option
if search_group is True:
    if group_name_search is not '':  # Group name to look for
        logger("Looking for group name '%s' in yaml file '%s'" % (group_name_search, script_path + "/" + group_yaml_filename), "debug")
        if os.path.exists(script_path + "/" + group_yaml_filename) and os.path.isfile(script_path + "/" + group_yaml_filename):
            try:
                stream = file(script_path + "/" + group_yaml_filename, 'r')
                group_in_file = yaml.safe_load(stream)
            except:  # Default group file does not exist!
                logger("Error reading group name '%s' from file '%s'! Exiting script" % (group_name_search, script_path + "/" + group_yaml_filename), "debug")
                printstring = "Error reading group name '%s' from file '%s'! Exiting script" % (group_name_search, script_path + "/" + group_yaml_filename)
                print("{0}".format(colored(printstring, 'red')))
                quit(2)
            logger("group_in_file = '%s'" % group_in_file, "debug")
            # print group_in_file
            # print "----------"
            # yaml.dump(group_in_file, sys.stdout)
            group_name_found = False
            try:  # Check if group name is in the group file and is a Dictionary
                for k, group_search_list in group_in_file.iteritems():
                    if k == group_name_search:
                        logger("Found group name '%s' in file '%s'" % (group_name_search, script_path + "/" + group_yaml_filename), "debug")
                        printstring = group_search_list['GroupDescription']
                        print("{0}".format(colored(printstring, 'green')))
                        loop_index = 0
                        for k, v in group_search_list.iteritems():
                            if k == 'Hosts':
                                for x in v:
                                    # List of items per host, items in this order: ssh username, ssh ip, ssh key, tag: Name (above)
                                    host_items = []
                                    index_num += 1
                                    tagname = x['Name']
                                    tagenvironment = x['Environment']
                                    tagsshkey = x['KeyName']
                                    instanceid = x['InstanceID']
                                    ip_address = x['IP']
                                    key_name = x['KeyName']
                                    shortcut = x['Shortcut']
                                    # Print 'unknown' for state since this list is not from api we do not know if the instance is running or not
                                    print(
                                        "{:<5}\tId: {:<25}\tState: {:^15}\tIP: {:<20}  \tName: {:<35}  \tEnv: {:<35}  \tKey: {:<15}".format(
                                            colored(index_num, 'cyan'),
                                            colored(instanceid, 'cyan'),
                                            colored('unknown', 'green'),
                                            colored(ip_address, 'red'),
                                            colored(tagname, 'green'),
                                            colored(tagenvironment, 'green'),
                                            colored(key_name, 'green')
                                        ))
                                    host_items.append(x['SSHUser'])
                                    host_items.append(ip_address)
                                    host_items.append(key_name)
                                    host_items.append(tagname)
                                    host_items.append(shortcut)
                                    returned_hosts[str(index_num)] = host_items
                                    loop_index += 1
                        group_name_found = True
                        break
            except TypeError as err:
                logger("Dictionary type not found for group_in_file: %s  Exiting script" % err, "critical")
                printstring = "Dictionary type not found for group_in_file: %s  Exiting script" % (err)
                print("{0}".format(colored(printstring, 'red')))
                quit(1)
            except AttributeError as err:
                logger("Dictionary attribute not found for group_in_file: %s  Exiting script" % err, "critical")
                printstring = "Dictionary attribute not found for group_in_file: %s  Exiting script" % (err)
                print("{0}".format(colored(printstring, 'red')))
                quit(1)
            except KeyError as err:
                logger("Dictionary value not found for group_in_file: %s  Exiting Script" % err, "critical")
                printstring = "Dictionary value not found for group_in_file: %s  Exiting script" % (err)
                print("{0}".format(colored(printstring, 'red')))
                quit(1)
            if group_name_found is False:
                logger("Group name '%s' not found in '%s'! Exiting script" % (group_name_search, script_path + "/" + group_yaml_filename), "critical")
                printstring = "Group name '%s' not found in '%s'! Exiting script" % (group_name_search, script_path + "/" + group_yaml_filename)
                print("{0}".format(colored(printstring, 'red')))
                quit(1)
            try:
                if len(group_search_list) == 0:
                    logger("Group name '%s' not found in '%s'! Exiting script" % (group_name_search, script_path + "/" + group_yaml_filename), "critical")
                    printstring = "Group name '%s' not found in '%s'! Exiting script" % (group_name_search, script_path + "/" + group_yaml_filename)
                    print("{0}".format(colored(printstring, 'red')))
                    quit(1)
            except:
                printstring = "Group name '%s' not found in '%s'! Exiting script" % (group_name_search, script_path + "/" + group_yaml_filename)
                print("{0}".format(colored(printstring, 'red')))
                quit(1)
            # Host list is printed to screen now continue on to menu choice
        else:
            logger("Group yaml file '%s' does not exist, unable to use -g switch! Exiting script" % script_path + "/" + group_yaml_filename, "critical")
            printstring = "Group yaml file '%s' does not exist, unable to use -g switch! Exiting script" % (script_path + "/" + group_yaml_filename)
            print("{0}".format(colored(printstring, 'red')))
            quit(1)

# Show group of hosts to ssh to from -e -n -k -i -v cli options
#   Do api call to AWS for a list of running hosts
#   Display those hosts that match query from given cli option
#   Display all hosts if no cli options given
if search_group is False:
    try:  # Loop over all EC2 instance data and output it to screen
        for instance in ec2_instances['Reservations']:  # List containing dictionaries of instances
            for host in instance['Instances']:
                host_items = []
                index_num += 1
                running = True  # Only show instances in 'running' state
                missing_tag_keyname = False
                tagname = ""  # Tag: Name
                tagenvironment = ""  # Tag: Environment
                tagsshuser = ""  # Tag: SSHUser (custom tag that specifies what ssh user to use)
                # Get instance info: instance id, ssh KeyName, instance state, instance private ip
                #   If value not found, will be blank in output
                try:
                    instance_id = str(host['InstanceId'])  # Instance Id
                    instance_sshkey = str(host['KeyName'])  # Key pair name
                    instance_state = str(host['State']['Name'])  # Instance state: running/stopped/terminated
                    instance_private_ip = str(host['PrivateIpAddress'])  # Instance private ip address
                    instance_vpc_id = str(host['VpcId'])  # Instance vpc id
                except KeyError as tagkeyerr:
                    logger("Missing a tag key '%s' for instanceid %s" % (tagkeyerr, host['InstanceId']), "warning")
                    if tagkeyerr is 'KeyName':
                        missing_tag_keyname = True
                        instance_sshkey = ''
                # Loop over tags for the instance and get Name, Environment, SSHUser
                try:
                    for i in host['Tags']:  # List containing dictionaries of tags
                        for dkey, dvalue in i.iteritems():  # Loop over dictionary key/values
                            if dkey == 'Key' and dvalue == 'Name':
                                tagname = i['Value']
                            elif dkey == 'Key' and dvalue == 'Environment':
                                tagenvironment = i['Value']
                            elif dkey == 'Key' and dvalue == 'SSHUser':
                                tagsshuser = i['Value']
                except KeyError as tagerr:
                    logger("Instance id '%s' has no tags, tag error: %s" % (instance_id, tagerr), "warning")
                    continue
                # Loop through instances and get OS user that we will ssh to
                # Datastax/Cassandra nodes require 'centos' user
                # AWS ami requires 'ec2-user' user
                if tagsshuser == "":
                    if re.search("datastax", tagname, re.IGNORECASE) or re.search("cassandra", tagname, re.IGNORECASE) \
                            or re.search("datastax", tagenvironment, re.IGNORECASE) or re.search("cassandra", tagenvironment, re.IGNORECASE):
                        tagsshuser = "centos"
                    else:
                        tagsshuser = "ec2-user"
                host_items.append(tagsshuser)
                #
                # Now start pairing down the list
                #   Search by vpc, ssh key, name, environment
                #   If no search specified, output all hosts
                #
                if search_vpc is True:  # Search by vpcid
                    if instance_state == 'running' and search_ip is False:  # Only show running instances
                        if instance_vpc_id in vpc_search:
                            print(
                                "{:<5}\tId: {:<25}\tState: {:^15}\tIP: {:<20}  \tName: {:<35}  \tEnv: {:<35}  \tKey: {:<15}".format(
                                    colored(index_num, 'cyan'),
                                    colored(instance_id, 'cyan'),
                                    colored(instance_state, 'green'),
                                    colored(instance_private_ip, 'red'),
                                    colored(tagname, 'green'),
                                    colored(tagenvironment, 'green'),
                                    colored(instance_sshkey, 'green')
                                ))
                            host_items.append(instance_private_ip)
                            host_items.append(instance_sshkey)
                            host_items.append(tagname)
                            returned_hosts[str(index_num)] = host_items
                elif key_search is True:  # Search by ssh keys tag and show all instances that match the local ssh keys
                    if default_vpc is True:  # Using vpc id from qq-defaults file
                        if instance_state == 'running' and search_ip is False and instance_vpc_id in vpc_search:  # Only show running instances
                            for key in ssh_keys_list:
                                try:  # Look for ssh key instances that match the ssh keys installed on this host
                                    result = re.search(key, instance_sshkey, re.IGNORECASE)
                                except TypeError:  # Was unable to perform search due to missing data in field
                                    logger("Regex search field empty or not searchable:  tagname=%s  tagenvironment=%s  key=%s  instance_sshkey=%s" % (tagname, tagenvironment, key, instance_sshkey), "critical")
                                    continue
                                if result:
                                    if instance_state == 'running':
                                        print(
                                            "{:<5}\tId: {:<25}\tState: {:^15}\tIP: {:<20}  \tName: {:<35}  \tEnv: {:<35}  \tKey: {:<15}".format(
                                                colored(index_num, 'cyan'),
                                                colored(instance_id, 'cyan'),
                                                colored(instance_state, 'green'),
                                                colored(instance_private_ip, 'red'),
                                                colored(tagname, 'green'),
                                                colored(tagenvironment, 'green'),
                                                colored(instance_sshkey, 'green')
                                            ))
                                        host_items.append(instance_private_ip)
                                        host_items.append(instance_sshkey)
                                        host_items.append(tagname)
                                        returned_hosts[str(index_num)] = host_items
                    else:
                        if instance_state == 'running' and search_ip is False:  # Only show running instances
                            for key in ssh_keys_list:
                                try:  # Look for ssh key instances that match the ssh keys installed on this host
                                    result = re.search(key, instance_sshkey, re.IGNORECASE)
                                except TypeError:  # Was unable to perform search due to missing data in field
                                    logger("Regex search field empty or not searchable:  tagname=%s  tagenvironment=%s  key=%s  instance_sshkey=%s" % (tagname, tagenvironment, key, instance_sshkey), "critical")
                                    continue
                                if result:
                                    if instance_state == 'running':
                                        print(
                                            "{:<5}\tId: {:<25}\tState: {:^15}\tIP: {:<20}  \tName: {:<35}  \tEnv: {:<35}  \tKey: {:<15}".format(
                                                colored(index_num, 'cyan'),
                                                colored(instance_id, 'cyan'),
                                                colored(instance_state, 'green'),
                                                colored(instance_private_ip, 'red'),
                                                colored(tagname, 'green'),
                                                colored(tagenvironment, 'green'),
                                                colored(instance_sshkey, 'green')
                                            ))
                                        host_items.append(instance_private_ip)
                                        host_items.append(instance_sshkey)
                                        host_items.append(tagname)
                                        returned_hosts[str(index_num)] = host_items
                elif search_name is True:  # Search for instance by Name tag
                    result = re.search(name_search, tagname, re.IGNORECASE)
                    if result:
                        if default_vpc is True:  # Using vpc id from qq-defaults file
                            if instance_state == 'running' and search_ip is False and instance_vpc_id in vpc_search:
                                print(
                                    "{:<5}\tId: {:<25}\tState: {:^15}\tIP: {:<20}  \tName: {:<35}  \tEnv: {:<35}  \tKey: {:<15}".format(
                                        colored(index_num, 'cyan'),
                                        colored(instance_id, 'cyan'),
                                        colored(instance_state, 'green'),
                                        colored(instance_private_ip, 'red'),
                                        colored(tagname, 'green'),
                                        colored(tagenvironment, 'green'),
                                        colored(instance_sshkey, 'green')
                                    ))
                                host_items.append(instance_private_ip)
                                host_items.append(instance_sshkey)
                                host_items.append(tagname)
                                returned_hosts[str(index_num)] = host_items
                        else:
                            if instance_state == 'running' and search_ip is False:
                                print(
                                    "{:<5}\tId: {:<25}\tState: {:^15}\tIP: {:<20}  \tName: {:<35}  \tEnv: {:<35}  \tKey: {:<15}".format(
                                        colored(index_num, 'cyan'),
                                        colored(instance_id, 'cyan'),
                                        colored(instance_state, 'green'),
                                        colored(instance_private_ip, 'red'),
                                        colored(tagname, 'green'),
                                        colored(tagenvironment, 'green'),
                                        colored(instance_sshkey, 'green')
                                    ))
                                host_items.append(instance_private_ip)
                                host_items.append(instance_sshkey)
                                host_items.append(tagname)
                                returned_hosts[str(index_num)] = host_items
                elif search_environment is True:  # Search for instance by Environment tag
                    result = re.search(env_search, tagenvironment, re.IGNORECASE)
                    if result:
                        if default_vpc is True:  # Using vpc id from qq-defaults file
                            if instance_state == 'running' and search_ip is False and instance_vpc_id in vpc_search:
                                print(
                                    "{:<5}\tId: {:<25}\tState: {:^15}\tIP: {:<20}  \tName: {:<35}  \tEnv: {:<35}  \tKey: {:<15}".format(
                                        colored(index_num, 'cyan'),
                                        colored(instance_id, 'cyan'),
                                        colored(instance_state, 'green'),
                                        colored(instance_private_ip, 'red'),
                                        colored(tagname, 'green'),
                                        colored(tagenvironment, 'green'),
                                        colored(instance_sshkey, 'green')
                                    ))
                                host_items.append(instance_private_ip)
                                host_items.append(instance_sshkey)
                                host_items.append(tagname)
                                returned_hosts[str(index_num)] = host_items
                        else:
                            if instance_state == 'running' and search_ip is False:
                                print(
                                    "{:<5}\tId: {:<25}\tState: {:^15}\tIP: {:<20}  \tName: {:<35}  \tEnv: {:<35}  \tKey: {:<15}".format(
                                        colored(index_num, 'cyan'),
                                        colored(instance_id, 'cyan'),
                                        colored(instance_state, 'green'),
                                        colored(instance_private_ip, 'red'),
                                        colored(tagname, 'green'),
                                        colored(tagenvironment, 'green'),
                                        colored(instance_sshkey, 'green')
                                    ))
                                host_items.append(instance_private_ip)
                                host_items.append(instance_sshkey)
                                host_items.append(tagname)
                                returned_hosts[str(index_num)] = host_items
                else:  # No search parameters given, return all hosts
                    if default_vpc is True:  # Using vpc id from qq-defaults files
                        if instance_state == 'running' and instance_vpc_id in vpc_search:
                            if search_ip is False:
                                print(
                                    "{:<5}\tId: {:<25}\tState: {:^15}\tIP: {:<20}  \tName: {:<35}  \tEnv: {:<35}  \tKey: {:<15}".format(
                                        colored(index_num, 'cyan'),
                                        colored(instance_id, 'cyan'),
                                        colored(instance_state, 'green'),
                                        colored(instance_private_ip, 'red'),
                                        colored(tagname, 'green'),
                                        colored(tagenvironment, 'green'),
                                        colored(instance_sshkey, 'green')
                                    ))
                                host_items.append(instance_private_ip)
                                host_items.append(instance_sshkey)
                                host_items.append(tagname)
                                returned_hosts[str(index_num)] = host_items
                            else:
                                if ip_search == instance_private_ip:
                                    # Found host ip matching ip given to search for
                                    host_items.append(instance_private_ip)
                                    host_items.append(instance_sshkey)
                                    host_items.append(tagname)
                                    returned_hosts[str(index_num)] = host_items
                    else:  # No search parameters given and no qq-defaults file in use
                        if instance_state == 'running':
                            if search_ip is False:
                                print(
                                    "{:<5}\tId: {:<25}\tState: {:^15}\tIP: {:<20}  \tName: {:<35}  \tEnv: {:<35}  \tKey: {:<15}".format(
                                        colored(index_num, 'cyan'),
                                        colored(instance_id, 'cyan'),
                                        colored(instance_state, 'green'),
                                        colored(instance_private_ip, 'red'),
                                        colored(tagname, 'green'),
                                        colored(tagenvironment, 'green'),
                                        colored(instance_sshkey, 'green')
                                    ))
                                host_items.append(instance_private_ip)
                                host_items.append(instance_sshkey)
                                host_items.append(tagname)
                                returned_hosts[str(index_num)] = host_items
                            else:
                                if ip_search == instance_private_ip:
                                    host_items.append(instance_private_ip)
                                    host_items.append(instance_sshkey)
                                    host_items.append(tagname)
                                    returned_hosts[str(index_num)] = host_items
    # Host list is printed to screen now continue on to menu choice
    except KeyboardInterrupt:
        logger("CTRL-C pressed! Exiting script", "info")
        printstring = "\r\nCTRL-C pressed! Exiting script"
        print("{0}".format(colored(printstring, 'red')))
        quit(0)
    except EndpointConnectionError as err:
        logger("Unable to connect to AWS EC2 api in specified region '%s'! Error: %s   Exiting script" % (aws_region, err), "critical")
        printstring = "Unable to connect to AWS EC2 api in specified region '%s'! Error: %s   Exiting script" % (aws_region, err)
        print("{0}".format(colored(printstring, 'red')))
        quit(2)
    except IOError as err:
        logger("IOError: %s during display of hosts (maybe used less/more or pipe)" % err, "critical")
        printstring = "IOError: %s during display of hosts (maybe used less/more or pipe)" % (err)
        print("{0}".format(colored(printstring, 'red')))
        quit(2)
    except ClientError as err:
        logger("Boto3 error: %s" % err, "critical")
        printstring = "Boto3 error: %s" % (err)
        print("{0}".format(colored(printstring, 'red')))
        quit(2)

# If instances were printed to screen then give option to ssh to them
#   returned_hosts should contain the right things in the right elements:
#   ssh ip   = returned_hosts[get_host_num][1]
#   ssh_key  = returned_hosts[get_host_num][2] + ".pem"
#   ssh_user = returned_hosts[get_host_num][0]
#   tag_name = returned_hosts[get_host_num][3]
num_of_hosts = len(returned_hosts.keys())
if num_of_hosts > 0:
    # Check if we're just connecting to a specific ip address and just querying for the key to use
    if search_ip is True:
        try:
            ssh_key = returned_hosts.values()[0][2] + ".pem"
        except IndexError:  # The provided ip address did not match any hosts returned
            printstring = "Ip address provided did not match any hosts we searched for!  Exiting script"
            print("{0}".format(colored(printstring, 'red')))
            logger("Ip address provided did not match any hosts we searched for!  Exiting script", "info")
            quit(2)
        ssh_ip = returned_hosts.values()[0][1]
        ssh_dir = os.path.expanduser('~/.ssh')
        ssh_user = returned_hosts.values()[0][0]
        tag_name = returned_hosts.values()[0][3]
        logger("Checking if ssh key file '%s' exists" % (ssh_dir + "/" + ssh_key), "debug")
        if os.path.isfile(ssh_dir + "/" + ssh_key) is True:  # Check if the ssh key file exists
            logger("Ssh'ing to %s@%s with key file: %s name: %s" % (ssh_user, ssh_ip, ssh_key, tag_name), "info")
            printstring = "Ssh'ing to %s@%s with key file: %s name: %s" % (ssh_user, ssh_ip, ssh_key, tag_name)
            print("{0}".format(colored(printstring, "green")))
            try:
                sshtohost(ssh_dir + "/" + ssh_key, ssh_ip, ssh_user)
            except KeyboardInterrupt:
                logger("CTRL-C pressed! Exiting script", "info")
                printstring = "\r\nCTRL-C pressed! Exiting script"
                print("{0}".format(colored(printstring, 'red')))
                quit(0)
        else:
            logger("Ssh key file '%s' does not exist!" % (ssh_dir + "/" + ssh_key), "critical")
            printstring = "SSH key file '%s/%s' does not exist! Exiting script" % (ssh_dir, ssh_key)
            print("{0}".format(colored(printstring, "red")))
            quit(2)
        quit(0)
    logger("Printed to screen '%d' hosts, now get which one to ssh to" % num_of_hosts, "debug")
    try:  # Catch CTRL-C by user
        try:
            get_host_num = raw_input("Type number of host to ssh to or q to quit> ")
        except EOFError as err:
            printstring = "Bye!"
            print("{0}".format(colored(printstring, 'green')))
            quit(0)
        get_host_num = str(get_host_num)
        if get_host_num == "q" or get_host_num == "Q" or get_host_num == "exit" or get_host_num == "quit":
            logger("Quit command given, exiting script", "info")
            printstring = "Bye!"
            print("{0}".format(colored(printstring, 'green')))
            quit(0)
        else:
            try:  # Check for KeyError, this catches if an invalid number or character was given to the raw_input
                ssh_key = returned_hosts[get_host_num][2] + ".pem"
            except KeyError:
                logger("Invalid number or character given '%s', Exiting script" % get_host_num, "critical")
                printstring = "Invalid number or character given '%s', Exiting script" % (get_host_num)
                print("{0}".format(colored(printstring, 'red')))
                quit(2)
            ssh_ip = returned_hosts[get_host_num][1]
            ssh_dir = os.path.expanduser('~/.ssh')
            ssh_user = returned_hosts[get_host_num][0]
            tag_name = returned_hosts[get_host_num][3]
            logger("Checking if ssh key file '%s' exists" % (ssh_dir + "/" + ssh_key), "debug")
            if os.path.isfile(ssh_dir + "/" + ssh_key) is True:  # Check if the ssh key file exists
                logger("Ssh'ing to %s@%s with key file: %s name: %s" % (ssh_user, ssh_ip, ssh_key, tag_name), "info")
                printstring = "Ssh'ing to %s@%s with key file: %s name: %s" % (ssh_user, ssh_ip, ssh_key, tag_name)
                print("{0}".format(colored(printstring, "green")))
                try:
                    sshtohost(ssh_dir + "/" + ssh_key, ssh_ip, ssh_user)
                except KeyboardInterrupt:
                    logger("CTRL-C pressed! Exiting script", "info")
                    printstring = "\r\nCTRL-C pressed! Exiting script"
                    print("{0}".format(colored(printstring, 'red')))
                    quit(0)
            else:
                logger("Ssh key file '%s' does not exist!" % (ssh_dir + "/" + ssh_key), "critical")
                printstring = "SSH key file '%s/%s' does not exist! Exiting script" % (ssh_dir, ssh_key)
                print("{0}".format(colored(printstring, "red")))
                quit(2)
            quit(0)
    except KeyboardInterrupt:
        logger("CTRL-C pressed! Exiting script", "info")
        printstring = "\r\nCTRL-C pressed! Exiting script"
        print("{0}".format(colored(printstring, 'red')))
        quit(0)
else:
    logger("No hosts returned!", "info")
    print("{0}".format(colored("No hosts returned!", "red")))
    quit(0)
