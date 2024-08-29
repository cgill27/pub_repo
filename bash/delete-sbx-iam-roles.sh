#!/bin/bash

# This script loops over all IAM role names with -sbx- in its name and deletes them
# This script is usually only used to cleanup after a failed Terraform sandbox destroy

# Get list of IAM roles
for role in $(aws --profile development --region us-east-2 iam list-roles | jq -r '.Roles[] | select(.RoleName|match("-sbx-.")) | .Arn'); do
    sbxARNRoles+=("${role}")
done

# Detach attached policies from roles and delete inline policies on roles
for role in "${sbxARNRoles[@]}"; do
    roleName=$(echo "${role}" | awk -F'/' '{print $2}')
    sbxNameRoles+=("${roleName}")
    echo "Removing attached policies for role: ${roleName}"
    role_attached_policies=$(aws --profile development --region us-east-2 iam list-attached-role-policies --role-name "${roleName}" --query 'AttachedPolicies[*].PolicyArn' --output text)
    for policy_arn in $role_attached_policies; do
        aws --profile development --region us-east-2 iam detach-role-policy --role-name "${roleName}" --policy-arn "${policy_arn}"
        echo "Detached policy ${policy_arn} from role ${roleName}"
    done
    echo "Removing inline policies for role: ${roleName}"
    role_inline_policies=$(aws --profile development --region us-east-2 iam list-role-policies --role-name "${roleName}" --query 'PolicyNames' --output text)
    for policy_name in $role_inline_policies; do
        aws --profile development --region us-east-2 iam delete-role-policy --role-name "${roleName}" --policy-name "${policy_name}"
        echo "Deleted inline policy ${policy_arn} from role ${roleName}"
    done
done

# Delete IAM roles
for i in "${sbxNameRoles[@]}"; do
    echo "Deleting role: $i"
    aws --profile development --region us-east-2 iam delete-role --role-name "$i"
done

exit