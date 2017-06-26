#!/usr/bin/python3

# This script is used by the monioring/check-seslimits Jenkins job

import boto3
import argparse
import sys


# Takes in a string with a threshold expressed as "percent,label" and returns
# a tuple with the percentage as a float as the first item and the label
# as a string as the second item
# "20,foobar" -> (20, "foobar")
def parse_threshold(value):
    r = value.split(',')
    return (float(r[0]), r[1])


# Copied from https://stackoverflow.com/a/41153081
class ExtendAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        items = getattr(namespace, self.dest) or []
        items.extend(values)
        setattr(namespace, self.dest, items)


class ThresholdAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        thresholds = getattr(namespace, self.dest) or []
        thresholds.extend([parse_threshold(t) for t in values])
        # Thresholds will be tested in order,
        # so they must be in descending order
        # Threshold values are expressed as a percentage of the 24 hour limit
        thresholds.sort(reverse=True)
        setattr(namespace, self.dest, thresholds)


parser = argparse.ArgumentParser()
parser.add_argument('-t', '--threshold', dest='thresholds', nargs='+',
                    action=ThresholdAction, required=True)
parser.add_argument('-r', '--region', dest='regions', nargs='+',
                    action=ExtendAction, required=True)
args = parser.parse_args()

exit_code = 0

session = boto3.session.Session()
for region in args.regions:
    ses = session.client('ses', region_name=region)
    data = ses.get_send_quota()
    limit = data["Max24HourSend"]
    current = data["SentLast24Hours"]
    percent = current/limit
    out_str = str(current) + "/" + str(limit) + " (" + str(percent) + "%)"

    for (threshold, label) in args.thresholds:
        if percent > threshold:
            print(region + " " + out_str + " - " + label)
            exit_code += 1
            break

sys.exit(exit_code)
