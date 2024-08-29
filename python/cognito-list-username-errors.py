#!/usr/bin/env python3

# This script takes three arguments and loops over all users in Cognito 
#   and writes to text file those that have a mismatch between their usernames and email ids
#
#   Input arg1: aws region
#   Input arg2: cognito pool id
#   Input arg3: file name to write to

import boto3
from botocore.config import Config
import argparse
import os
import re

# Check Python version
req_version = (3, 9)
cur_version = os.sys.version_info

if not cur_version >= req_version:
    print('Your Python interpreter is too old. Please consider upgrading to atleast 3.9')
    exit(2)

script_name = os.path.basename(__file__)

# Get cli arguments
parser = argparse.ArgumentParser(description="Loop over users in Cognito and write to Text file those who have a mismatch between their username and emails")
parser.add_argument("region", help="AWS Region", type=str)
parser.add_argument("cognitopool", help="AWS Cognito User Pool ID", type=str)
parser.add_argument("file", help="File name as output", type=str)
parser.add_argument("--awsprofile", help="AWS Profile name", type=str)
args = parser.parse_args()
region = args.region
cognito_pool = args.cognitopool
output_file = args.file
if args.awsprofile:
    aws_profile = args.awsprofile

print(f'Starting {script_name} script')
print(f'AWS Region: {region}')
print(f'Cognito Pool ID: {cognito_pool}')
print(f'Output File Name: {output_file}')
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

# Make a boto3 connection to Cognito IDP
try:
    client = boto3.client('cognito-idp', config=my_config)
except Exception as error:
    print(f'Error: {error}')
    exit(2)

# Keep counts
username_mismatch_counts = 0
username_mismatch_list = []
total_users = 1
pagination_count = 0
pagination_token = ""
next_pagination_token = ""

# While loop to list_users call with pagination
# AWS allows a maximum of 60 users per call
while next_pagination_token is not None:
    if pagination_token == "":
        pagination_count += 1
        try:
            response = client.list_users(
                UserPoolId=cognito_pool,
                # AttributesToGet=[
                #     'email', 'email_verified', 'phone_number', 'phone_number_verified', 'name', 'family_name'
                # ],
                Limit=60
            )
        except Exception as error:
            print(f'Error: {error}')
            exit(2)
    else:
        pagination_count += 1
        try:
            response = client.list_users(
                UserPoolId=cognito_pool,
                # AttributesToGet=[
                #     'email', 'email_verified', 'phone_number', 'phone_number_verified', 'name', 'family_name'
                # ],
                Limit=60,
                PaginationToken=pagination_token
            )
        except Exception as error:
            print(f'Error: {error}')
            exit(2)
    # Loop through all users
    for user in response['Users']:
        total_users += 1
        user_attributes = { attr['Name']:attr['Value'] for attr in user['Attributes'] }
        ideal_username = re.sub("[@.]", "|", user_attributes['email'])
        actual_username = user['Username']
        if ideal_username != actual_username:
            username_mismatch_counts += 1
            username_mismatch_list.append(user_attributes['email'])
    # Check for pagination token returned in the response and go again if it exists
    try:
        if len(response['PaginationToken']) > 0:    
            pagination_token = response['PaginationToken']
        else:
            next_pagination_token = None
    except KeyError:
        next_pagination_token = None

# Print out totals
print(f'Total users: {total_users}')
print(f'Username mismatch count: {username_mismatch_counts}')

print('')
if len(username_mismatch_list) == 0:
    print('No mismatched users found')
    exit(0)

# Loop over dictionary to create a csv file with items in a specified order
with open(output_file, 'w') as file:
    for email in username_mismatch_list:
        file.write(email+'\n')
file.close()
