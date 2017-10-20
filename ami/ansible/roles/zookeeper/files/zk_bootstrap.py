import argparse
import requests

import boto3
import botocore

'''

This script is intended to configure and bootstrap the zookeeper cluster.

For the bootstrapping we require two files to be configured:
   - File that contains the machine id:
       {ZK_DATA_DIR}/myid
   - File that contains the list of servers:
       {ZK_CONF_DIR}/zoo.dynamic.cfg


Challenges:

 1. Fresh vs Existing bootstrap:

   Determining if a fresh bootstrap of a zookeeper cluster
   is needed or the there exists a cluster but needs
   dynamic reconfiguration to allow this current host
   to participate in the cluster.

   - Fresh bootstrap means, there is no zookeeper cluster
   or nodes are just started and need to form a cluster.
     - In this case, the active zookeepers would need
       to generate the {ZK_CONF_DIR}/zoo.dynamic.cfg and
       use that to form the cluster.

   - Dynamic Reconfiguration means there is a zookeeper cluster
   that this host can connet to and using that connection
   add itself to the cluster.

 2. Assigning unique zookeeper id:

   The challenge with this is to somehow not have clashing zookeeper ids
   which means we would need to avoid any kind of race condition if possible
   so that no two zookeeper instances share the same id.

   The id must be decided upon boot. For a fresh launch of the instance,
   it should pick an unclaime id that no other zookeeper instance has claimed.
   For a restart of the same instance, it should use the already assinged
   zookeeper id.

   Once the id is assigned we determine whether it is a fresh bootstrap of the
   cluster or just a dynamic configuration is needed and accordingly proceed
   to the bootstrap process.

 3. Removing terminated zookeeper instances

   We need a way to remove zookeeper instances that were once part of the
   cluster after they have been terminated otherwise they would
   zookeeper would think they are part of the cluster but unavailable
   and hence it would break the quorum.

'''

ZK_ID_TAG = 'zookeeper_id'
ZK_LOG_GROUP = '/zookeeper/instances'


def get_instance_id():
   ''' Returns the current EC2's instance id. '''
   resp = requests.get('http://169.254.169.254/latest/meta-data/instance-id')
   instance_id = resp.text
   return instance_id


def get_zookeeper_instances():
   ''' Returns instances of zookeeper '''


def get_zookeeper_id(region, log_group):
   ''' Gets an unclaimed zookeeper id that is unique and which does not
   clash with any functional zookeeper id. It guarantees this property
   with the help of CloudWatch Logs.
   '''
   cwlogs = boto3.client('logs', region)
   for zkid in range(1, 10):
      try:
         cwlogs.create_log_stream(
            logGroupName=log_group,
            logStreamName=str(zkid)
         )
         return zkid
      except botocore.exceptions.ClientError as ex:
         if ex.response['Error']['Code'] == "ResourceAlreadyExistsException":
            continue
         else:
            raise
   raise Exception("No zookeeper id available")


def get_tag(region, instance_id, tag_key):
   ''' Gets the current EC2 zookeeper_id tag on the current instance
   if there is any tag set. '''
   ec2 = boto3.client('ec2', region)
   response = ec2.describe_instances(InstanceIds=[instance_id])
   instance = response['Reservations'][0]['Instances'][0]
   tags = instance['Tags']
   tag_value = None
   for tag in tags:
      if tag["Key"] == tag_key:
         tag_value = tag["Value"]
   return tag_value


def set_tag(region, instance_id, tag_key, tag_value):
   ''' Sets the EC2 zookeeper_id tag on the current instance. '''
   ec2 = boto3.resource('ec2', region)
   tag = ec2.create_tags(
            Resources=[instance_id],
            Tags=[
               {
                  'Key': tag_key,
                  'Value': str(tag_value)
               }
            ]
         )


def save_zookeeper_id(filename, zookeeper_id):
   ''' Performs backup of existing file and saves the new
   configuration of zookeeper_id to the file.
   '''
   # Backup old configuration
   backup_filename = '{filename}.bk'.format(filename=filename)
   with open(backup_filename, 'w') as fwrite:
      with open(filename, 'r') as fread:
         content = fread.read()
      fwrite.write(content)

   # Save new configuration
   with open(filename, 'w') as fwrite:
      fwrite.write(zookeeper_id)


def do_bootstrap(region, id_file, dynamic_file):
   ''' Bootstraps the zookeeper cluster if it does not exists
   otherwise it bootstraps this instance to join the cluster
   via dynamic reconfiguration.
   '''
   # Get the zookeeper_id
   instance_id = get_instance_id()
   zookeeper_id = get_tag(region, instance_id, ZK_ID_TAG)
   if not zookeeper_id:
      zookeeper_id = get_zookeeper_id(region, ZK_LOG_GROUP)
      set_tag(region, instance_id, ZK_ID_TAG, zookeeper_id)
   save_zookeeper_id(id_file, zookeeper_id)

   # Determine if there is a cluster



def _parse_args():
    parser = argparse.ArgumentParser(
        prog='python zk_bootstrap',
        usage='%(prog)s [options]',
        description='Bootstrap script for the Zookeeper Ensemble.'
    )
    parser.add_argument(
        '--region',
        type=str,
        nargs=1,
        metavar=("<AWS_REGION>"),
        help='AWS Region.'
    )
    parser.add_argument(
        '--id-file',
        type=str,
        nargs=1,
        metavar=("<PATH-TO-ID-FILE>"),
        help='Path to the ID File.'
    )
    parser.add_argument(
        '--dynamic-file',
        type=str,
        nargs=1,
        metavar=("PATH-TO-DYNAMIC-FILE"),
        help='Path to the dynamic reconfig file.'
    )
    return parser


def main():
   ''' This program bootstraps the zookeeper cluster. If the cluster already
   exists and is functional, it will bootstrap this instance to join the
   cluster via dynamic reconfiguration.

   During the bootstrap, the zookeeper_id will be generated for this instance
   and saved to the ${ZOOKEEPER_DATA_DIR}/myid file.

   Also, the dynamic config will be generated for a fresh bootstrap if the
   cluster does not already exists otherwise the instance will join the
   existing cluster.

   To run bootstrap:

      zk_bootstrap --region <AWS-REGION> \
                   --id-file <PATH-TO-ID-FILE> \
                   --dynamic-file <PATH-TO-DYNAMIC-FILE>
   '''
   parser = _parse_args()
   args = vars(parser.parse_args())
   try:
      region = args['region'][0]
      id_file = args['id_file'][0]
      dynamic_file = args['dynamic_file'][0]
   except:
      parser.print_help()
      raise

   do_bootstrap(region, id_file, dynamic_file)


if __name__=='__main__':
   main()

# Determine fresh bootstrap or dynamic configuration

# Generate dynamic conf for fresh bootstrap

# Start zookeeper server (it will form the cluster)

# Check if successful, otherwise log error and exit 2

# Join zookeeper cluster if dynamic configuration is needed

# Remove old zookeeper machine that was terminated

# Start zookeeper server (it will participate in the cluster)

# Cron job for removing all inactive zookeeper ids
