#!/usr/bin/env python3

# This script takes two arguments and loops over all AWS Secrets Manager
#   secrets and shows any that have empty values
#
#   Input arg1: aws region
#   Input arg2: tag suffix for environment to query, ex. dev-ue2

import boto3
import sys
from botocore.config import Config
import json

if (args_count := len(sys.argv)) > 3:
    print(f"Two arguments expected, got {args_count - 1}")
    raise SystemExit(2)
elif args_count < 3:
    print("You must specify 2 arguments: aws region, and tag suffix")
    raise SystemExit(2)

print("Starting check-empty-aws-secrets.py script")
print(f'Region: {sys.argv[1]}')
print(f'Tag suffix: {sys.argv[2]}')

# Uncomment the following line to use a local aws profile
#boto3.setup_default_session(profile_name='staging')

my_config = Config(
    region_name = sys.argv[1],
    signature_version = 'v4',
    retries = {
        'max_attempts': 3,
        'mode': 'standard'
    }
)

try:
    client = boto3.client('secretsmanager', config=my_config)
except Exception as error:
    print(f'Error: {error}')
    exit(2)

# Fetch all secrets in the first 100 results
try:
    response = client.list_secrets(
        MaxResults=100,
        SortOrder='asc'
    )
except Exception as error:
    print(f'Error: {error}')
    exit(2)

# Add all secret names in the first 100 secrets to a list
secret_names_list = []
for secret in response['SecretList']:
    secret_names_list.append(secret['Name'])

# Fetch all secret names in the next 100 secrets if more than 100
try:
    if len(response['NextToken']) > 0:
        try:
            response = client.list_secrets(
                MaxResults=100,
                NextToken=response['NextToken'],
                SortOrder='asc'
            )
        except Exception as error:
            print(f'Error: {error}')
            exit(2)
        for secret in response['SecretList']:
            secret_names_list.append(secret['Name'])
except KeyError:
    #print('Found 100 or less secrets')
    pass

# Print out the total number of secrets we found
num_of_secrets = len(secret_names_list)
print(f'Retrieved {num_of_secrets} total secrets from {sys.argv[1]}\n')

# List of secrets to skip because we cannot parse their secret string for whatever reason
skip_secret_list = ["skip-secret-"]

skip_secret_list_full_name = []
for skip_secret in skip_secret_list:
    skip_secret_list_full_name.append(f'{skip_secret}{sys.argv[2]}')

print('Skipping these secret names (unable to parse secret string):')
print(skip_secret_list_full_name)
print('\n')

# Loop over all secret names check if any keys in secret have empty values and print out
for secret in secret_names_list:
    if secret.endswith(sys.argv[2]):
        skip_secret_name = secret.strip()
        print(f'Found secret: {skip_secret_name}')
        if skip_secret_name in skip_secret_list_full_name:
            print(f'Skipping secret: {skip_secret_name}')
            continue
        try:
            secret_value = client.get_secret_value(
                SecretId=secret
            )
        except Exception as error:
            print(f'Error: {error}')
            exit(2)
        secret_string = secret_value['SecretString']
        try:
            secret_string = json.loads(secret_string)
        except Exception as error:
            print(f'*** json.loads Error: {error}')
            continue
        for key, value in secret_string.items():
            if value == '':
                print(f'\tSecret "{secret}" has empty value for {key}')

print("Done")
exit(0)
