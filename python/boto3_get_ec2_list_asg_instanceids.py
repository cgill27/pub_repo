import sys
import boto3

if len(sys.argv) == 1:
    print "Missing required argument -- asg name"
    quit(2)

asg = sys.argv[1]

asg_client = boto3.client('autoscaling', region_name='us-east-1')
ec2_client = boto3.client('ec2', region_name='us-east-1')

asg_response = asg_client.describe_auto_scaling_groups(AutoScalingGroupNames=[asg])

instance_ids = [] # List of instance-ids

if len(asg_response['AutoScalingGroups']) > 0:
    for i in asg_response['AutoScalingGroups']:
        for k in i['Instances']:
            instance_ids.append(k['InstanceId'])
else:
    print "Autoscale group name '%s' not found! Exiting script" % asg
    quit(2)

if len(instance_ids) > 0:
    for x in instance_ids:
        print x,
else:
    print "No instances found in ASG! Exiting script"
    quit(2)
