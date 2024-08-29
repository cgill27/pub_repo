#!/usr/bin/env python3

# This script takes three arguments and deletes a specific tag from security groups
#   Input arg1: aws region
#   Input arg2: tag suffix for environment to query, ex. dev-ue2
#   Input arg3: node group name, ex. core

import boto3
import sys
from botocore.config import Config
import argparse
import os

# Check Python version
req_version = (3, 9)
cur_version = os.sys.version_info

if not cur_version >= req_version:
    print('Your Python interpreter is too old. Please consider upgrading to at least 3.9')
    exit(2)

script_name = os.path.basename(__file__)

# Get cli arguments
parser = argparse.ArgumentParser(description="Delete a specific tag from security groups")
parser.add_argument("region", help="AWS Region", type=str)
parser.add_argument("tag_suffix", help="AWS Tag Suffix", type=str)
parser.add_argument("node_group_name", help="EKS Node Group Name", type=str)
parser.add_argument("--awsprofile", help="AWS Profile name", type=str)
args = parser.parse_args()
region = args.region
tag_suffix = args.tag_suffix
node_group_name = args.node_group_name
if args.awsprofile:
    aws_profile = args.awsprofile

# Show script supplied arguments
print(f'Starting {script_name} script')
print(f'Region: {region}')
print(f'Tag suffix: {tag_suffix}')
print(f'Node group name: {node_group_name}')
if args.awsprofile:
    print(f'Using AWS Profile: {aws_profile}')

# Use an AWS profile if specified
if args.awsprofile:
    try:
        boto3.setup_default_session(profile_name=aws_profile)
    except Exception as error:
        print(f'Error: {error}')
        exit(2)

my_config = Config(
    region_name = region,
    signature_version = 'v4',
    retries = {
        'max_attempts': 3,
        'mode': 'standard'
    }
)

try:
    client = boto3.client('ec2', config=my_config)
except Exception as error:
    print(f'Error: {error}')
    exit(2)

group_name = f'{node_group_name}-eks-{tag_suffix}'

try:
    response = client.describe_security_groups()
except Exception as error:
    print(f'Error: {error}')
    exit(2)

num_of_sgs = len(response['SecurityGroups'])
print(f'Retrieved {num_of_sgs} total security groups')

for group in response['SecurityGroups']:
    #print(group_name) # core-eks-staging-ue2
    if group['GroupName'].startswith(group_name):
        # core-eks-staging-ue2-20220731234231387900000001
        print(f'Found security group {group["GroupName"]} to remove karpenter tag from')
        security_group_name = group['GroupName']
        security_group_id = group['GroupId']
        cluster_name = f'eks-{tag_suffix}'
        try:
            response = client.delete_tags(
                DryRun=False,
                Resources=[
                    security_group_id,
                ],
                Tags=[
                    {
                        'Key': 'karpenter.sh/discovery',
                        'Value': cluster_name
                    },
                ]
            )
            print(f'Successfully deleted tag from security group: {security_group_name}')
            exit(0)
        except Exception as error:
            print(f'Error: {error}')
            exit(2)
print('Did not find security group to remove karpenter tag from')        
