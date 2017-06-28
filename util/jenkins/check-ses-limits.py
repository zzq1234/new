#!/usr/bin/python3

# This script is used by the monioring/check-seslimits Jenkins job

import boto3
import argparse
import sys


# Copied from https://stackoverflow.com/a/41153081
class ExtendAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest) or []
        items.extend(values)
        setattr(namespace, self.dest, items)


parser = argparse.ArgumentParser()
parser.add_argument('-c', '--crit', required=True, type=float,
                    help="Critical threshold in percentage")
parser.add_argument('-w', '--warn', required=False, type=float,
                    help="Warning threshold in percentage (Optional)")
parser.add_argument('-r', '--region', dest='regions', nargs='+',
                    action=ExtendAction, required=True,
                    help="AWS regions to check")
args = parser.parse_args()

if args.warn and args.warn >= args.crit:
    print("ERROR: Warning threshold (" + str(args.warn) +
          ") >= Critical threshold (" + str(args.crit) + ")")
    sys.exit(1)

exit_code = 0

session = boto3.session.Session()
for region in args.regions:
    ses = session.client('ses', region_name=region)
    data = ses.get_send_quota()
    limit = data["Max24HourSend"]
    current = data["SentLast24Hours"]
    percent = current/limit
    out_str = str(current) + "/" + str(limit) + " (" + str(percent) + "%)"

    if percent >= args.crit:
        print(region + " " + out_str + " - CRITICAL!")
        exit_code += 1
    elif args.warn and percent >= args.warn:
        print(region + " " + out_str + " - WARNING!")
        exit_code += 1

sys.exit(exit_code)
