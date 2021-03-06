#!/usr/bin/env python

################################################################
#
# es-credentials.py - sets up credentials for evidence server 
#
# Usage: es-credentials.py [-h] --bucket evidence-server-01
#
# Examples:
#   ./es-credentials.py -a r -b govready-es-srv-01 -p govready-es-srv-01+read -u govready-es-srv-01+read
#   ./es-credentials.py -a w -b govready-es-srv-01 -p govready-es-srv-01+write -u govready-es-srv-01+write
#
# Creates bucket, policy, user, and access key, or uses existing ones if
# they already exist.  Prints user's access key ID and secret key to STDOUT.
#
# Required arguments:
#   -b, --bucket  evidence-server-01  name of evidence server bucket
#   -p, --policy  evidence-server-01-policy  name of policy
#   -a, --access  access permissions to include in policy: r, w, or rw
#   -u, --user USERNAME  user to create
#
# Optional arguments:
#   -h, --help    show this help message and exit
#
################################################################

# for control-C handling
import sys
import signal

# parse command-line arguments
import argparse

# AWS/S3 interface
import boto3
from botocore.exceptions import ClientError

# Gracefully exit on control-C
signal.signal(signal.SIGINT, lambda signal_number, current_stack_frame: sys.exit(0))

# IAM policies

iam_policies = {
"r":{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": "s3:ListAllMyBuckets",
            "Resource": "*"
        },
        {
            "Sid": "VisualEditor1",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetObject",
                "s3:GetObjectAcl",
                "s3:GetObjectTagging"
            ],
            "Resource": [
            ]
        }
    ]
},
"w":{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": "s3:ListAllMyBuckets",
            "Resource": "*"
        },
        {
            "Sid": "VisualEditor1",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:PutObject",
                "s3:PutObjectAcl",
                "s3:PutObjectTagging"
            ],
            "Resource": [
            ]
        }
    ]
},
"rw":{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": "s3:ListAllMyBuckets",
            "Resource": "*"
        },
        {
            "Sid": "VisualEditor1",
            "Effect": "Allow",
            "Action": [
                "s3:ListBucket",
                "s3:GetObject",
                "s3:GetObjectAcl",
                "s3:GetObjectTagging",
                "s3:PutObject",
                "s3:PutObjectAcl",
                "s3:PutObjectTagging"
            ],
            "Resource": [
            ]
        }
    ]
}
}

# Set up argparse
def init_argparse():
    parser = argparse.ArgumentParser(description='Sets up credentials for evidence server.')
    parser.add_argument('-b', '--bucket', required=True, help='name of evidence server bucket')
    parser.add_argument('-p', '--policy', required=True, help='name of policy')
    parser.add_argument('-a', '--access', help='access permissions to include in policy: r, w, or rw')
    parser.add_argument('-u', '--user', help='name of user')
    # TODO: consider specifying descriptions and tags
    return parser

def confirm_or_create_bucket(aws_region, s3, bucket_name):
    try:
        response = s3.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            try:
                if aws_region == 'us-east-1':
                    # no LocationConstraint is used if AWS region is 'us-east-1'
                    response = s3.create_bucket(
                        ACL='private',
                        Bucket=bucket_name
                        )
                else:
                    response = s3.create_bucket(
                        ACL='private',
                        Bucket=bucket_name,
                        CreateBucketConfiguration={
                            'LocationConstraint': aws_region
                            }
                        )
                if response["ResponseMetadata"]["HTTPStatusCode"] is not 200:
                    sys.stderr.write("{}\n".format(response))
                    sys.stderr.write("Error: bucket creation failed.\n")
                response = s3.put_public_access_block(
                    Bucket=bucket_name,
                    PublicAccessBlockConfiguration={
                        'BlockPublicAcls': True,
                        'IgnorePublicAcls': True,
                        'BlockPublicPolicy': True,
                        'RestrictPublicBuckets': True
                        }
                    )
            except Exception as e:
                sys.stderr.write("{}\n".format(e))
        else:
            sys.stderr.write("{}\n".format(e))

def confirm_or_create_policy(iam, args):
    arn = None
    try:
        response = iam.list_policies(Scope='Local')
        # TODO: use NextMarker to retrieve more than one page
        for policy in response["Policies"]:
            if policy["PolicyName"] == args.policy:
                arn = policy["Arn"]
        if arn is None:
            # policy was not found; let's create it
            if args.access in iam_policies.keys():
                iam_policy = iam_policies[args.access]
                iam_policy["Statement"][1]["Resource"] = [
                    "arn:aws:s3:::{}/*".format(args.bucket),
                    "arn:aws:s3:::{}".format(args.bucket)
                    ]
                response = iam.create_policy(
                    PolicyName=args.policy,
                    PolicyDocument=str(iam_policy).replace("'",'"')
                    )
                if response["ResponseMetadata"]["HTTPStatusCode"] is not 200:
                    sys.stderr.write("{}\n".format(response))
                    sys.stderr.write("Error: policy creation failed.\n")
                arn = response["Policy"]["Arn"]
            else:
                sys.stderr.write("Error: '--access' must be one of r, w, or rw.\n")
    except Exception as e:
        sys.stderr.write("{}\n".format(e))
    return arn

def main():
    argparser = init_argparse();
    args = argparser.parse_args();

# (sample messages to use at the right spot)
# WARNING: -r ignored because policy {} already exists.
# Attaching existing policy {}.

    # make s3 connections
    aws_region = 'us-east-1'
    iam = boto3.client('iam')
    s3 = boto3.client('s3', aws_region)
    sts = boto3.client('sts')

    # check API identity
    # TODO: get the account alias, too: http://boto.readthedocs.org/en/latest/ref/iam.html#boto.iam.connection.IAMConnection.get_account_alias
    response = sts.get_caller_identity()
    my_identity_account = response["Account"]
    my_identity_arn = response["Arn"].replace("arn:aws:iam::{}:".format(my_identity_account),"")
    sys.stderr.write('Using account #{}, "{}".\n'.format(my_identity_account, my_identity_arn))

    # make sure bucket exists
    confirm_or_create_bucket(aws_region, s3, args.bucket)

    # make sure policy exists
    arn = confirm_or_create_policy(iam, args)
        
    # make sure user exists
    try:
        response = iam.create_user(
            UserName=args.user,
            Tags=[
                {
                    'Key':'created-by',
                    'Value':'govready:es-credentials'
                    }
                ]
            )
    except ClientError as e:
        if e.response["Error"]["Code"] == 'EntityAlreadyExists':
            pass
        else:
            sys.stderr.write("{}\n".format(e))

    # attach policy
    if arn is None:
        sys.stderr.write("ERROR: Can't attach policy: no policy exists.\n")
    else:
        try:
            response = iam.attach_user_policy(
                UserName=args.user,
                PolicyArn=arn
                )
        except ClientError as e:
            sys.stderr.write("{}\n".format(e))

    # create access key
    try:
        response = iam.create_access_key(
            UserName=args.user
            )
        print("# for Windows, use 'set' instead of 'export'")
        print("export AWS_ACCESS_KEY_ID={}".format(response["AccessKey"]["AccessKeyId"]))
        print("export AWS_SECRET_ACCESS_KEY={}".format(response["AccessKey"]["SecretAccessKey"]))
    except ClientError as e:
        sys.stderr.write("{}\n".format(e))

if __name__ == "__main__":
    exit(main())
