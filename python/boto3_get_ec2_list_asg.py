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

ec2_response = ec2_client.describe_instances(
    InstanceIds = instance_ids
    )   

if len(ec2_response['Reservations']) > 0:
    private_ip = [] # List to hold the Private IP Address
    for instances in ec2_response['Reservations']:
        for ip in instances['Instances']:
            private_ip.append(ip['PrivateIpAddress'])
    print "\n".join(private_ip)
else:
    print "No instances found in autoscale group '%s'" % asg
