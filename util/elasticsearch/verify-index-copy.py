import requests
from argparse import ArgumentParser

description = """
Compare two Elasticsearch indices
"""

def parse_args():
  parser = ArgumentParser(description=description)

  parser.add_argument('-o', '--old', dest='old', required=True, nargs=2,
    help='Hostname and index of old ES host, e.g. https://localhost:9200 content')
  parser.add_argument('-n', '--new', dest='new', required=True, nargs=2,
    help='Hostname of new ES host, e.g. https://localhost:9200 content')

  return parser.parse_args()

def main():
  args = parse_args()

  #compare document count
  old = requests.get("{}/{}/_stats".format(*args.old))
  new = requests.get("{}/{}/_stats".format(*args.new))
  old.raise_for_status()
  new.raise_for_status()

  old_count = old.json()['_all']['total']['docs']['count']
  new_count = new.json()['_all']['total']['docs']['count']
  print "{}: Document count ({} = {})".format(
    old_count, new_count, 'OK' if old_count==new_count else 'FAILURE')

  old_size = old.json()['_all']['total']['storage']['size_in_bytes']
  new_size = new.json()['_all']['total']['storage']['size_in_bytes']
  print "{}: Index size ({} = {})".format(
    old_size, new_size, 'OK' if old_count==new_count else 'FAILURE')


"""
index.stats()
elasticsearch.scroll()
use without scan during downtime
elasticsearch.helpers.scan is an iterator (whew)

sample first, then full validation
  is old subset of new?
  is number of edits small?

no numeric ids
can use random scoring?
{"size": 1, "query": {"function_score": {"functions":[{"random_score": {"seed": 123456}}]}}}
use that with scroll and check some number
can't use scroll with sorting. Maybe just keep changing the seed?
  It's kinda slow, but probably fine
  get `size` at a time
  are random sorts going to get the same docs on both clusters?
Alternative: random score with score cutoff? Or script field and search/cutoff
  Might also be able to use track_scores with scan&scroll on 1.5 and a score cutoff
"""