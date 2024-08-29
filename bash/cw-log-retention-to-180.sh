#!/bin/bash

AWS_REGION="us-east-2"
AWS_PROFILE="dev"

log_groups=$(aws logs describe-log-groups --region $AWS_REGION --query 'logGroups[?retentionInDays == 'null'].[logGroupName]' --output text --profil $AWS_PROFILE)

for log_group in $log_groups; do
    aws logs put-retention-policy --region $AWS_REGION --log-group-name $log_group --retention-in-days 180 --profil $AWS_PROFILE 
done