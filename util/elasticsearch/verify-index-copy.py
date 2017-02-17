"""
Verifies that an index was correctly copied from one ES host to another.
"""

import itertools
import random

from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan
from argparse import ArgumentParser


description = """
Compare two Elasticsearch indices
"""

SCAN_ITER_STEP = 50

RANDOM_CHECK_SIZE = 10
RANDOM_CHECKS_BEFORE_RESET = 100

def parse_args():
    """
    Parse the arguments for the script.
    """
    parser = ArgumentParser(description=description)

    parser.add_argument(
        '-o', '--old', dest='old', required=True, nargs=2,
        help='Hostname and index of old ES host, e.g. https://localhost:9200 content'
    )
    parser.add_argument(
        '-n', '--new', dest='new', required=True, nargs=2,
        help='Hostname of new ES host, e.g. https://localhost:9200 content'
    )
    parser.add_argument(
        '-mt', '--match-threshold', dest='match_threshold', type=float, default=.9,
        help='Percentage of matching docs between old and new indices req. for an OK (default: .9)'
    )
    parser.add_argument(
        '-cp', '--check-percentage', dest='check_percentage', type=float, default=.1,
        help='Percentage of randomly found docs to check between old and new indices (default: .1)'
    )
    parser.add_argument(
        '-m', '--max-scan', dest='max_scan', type=int, default=100000,
        help='Number of documents to scan through in simple scan. (default: 100000)'
    )

    return parser.parse_args()


def grouper(iterable, n, fillvalue=None):
    """
    Collect data into fixed-length chunks or blocks
    from the import itertools recipe list: https://docs.python.org/3/library/itertools.html#recipes
    """
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return itertools.izip_longest(*args)


def find_matching_ids(es, index, ids):
    """
    Finds out how many of the ids in the given ids are in the given index in the given
    ES deployment.

    Args:
        es - Elasticsearch instance corresponding to the cluster we want to check
        index - name of the index that we want to check
        ids - a list of dictionaries of the form {'_id': <id>} of the ids we want to check.
    """
    body = {'docs': ids}

    search_result = es.mget(index=index, body=body)
    matching = 0
    for elt in search_result['docs']:
        # in ES 0.9.x
        if 'exists' in elt:
            matching += 1 if elt['exists'] else 0
        # in ES 1.x
        elif 'found' in elt:
            matching += 1 if elt['found'] else 0
    return matching


def main():
    """
    Run the verification.
    """
    args = parse_args()
    old_es = Elasticsearch([args.old[0]])
    new_es = Elasticsearch([args.new[0]])

    old_index = args.old[1]
    new_index = args.new[1]

    old_stats = old_es.indices.stats(index=args.old[1])['indices'].values()[0]['total']
    new_stats = new_es.indices.stats(index=args.new[1])['indices'].values()[0]['total']

    #compare document count
    old_count = old_stats['docs']['count']
    new_count = new_stats['docs']['count']

    print "{}: Document count ({} = {})".format(
        'OK' if old_count == new_count else 'FAILURE', old_count, new_count
    )

    old_size = old_stats['store']['size_in_bytes']
    new_size = new_stats['store']['size_in_bytes']
    print "{}: Index size ({} = {})".format(
        'OK' if old_count == new_count else 'FAILURE', old_size, new_size
    )

    matching = 0
    total = 0

    # Scan for matching documents

    # In order to match the two indeces without having to deal with ordering issues,
    # we pull a set of dcouments from the old ES index, and then try to find matching
    # documents with the same _id in the new ES index. This process is batched to avoid
    # making individual network calls to the new ES index.

    old_iter = scan(old_es, index=old_index)
    for old_elts in grouper(old_iter, SCAN_ITER_STEP):

        old_elt_ids = [{'_id': elt['_id']} for elt in old_elts if elt is not None]
        matching += find_matching_ids(new_es, new_index, old_elt_ids)
        total += len(old_elt_ids)
        if total % 100 == 0:
            print 'processed {} items'.format(total)

        if total > args.max_scan:
            print 'Completed max number of scanned comparisons.'
            break

    ratio = float(matching)/total
    print "{}: scanned documents matching ({} out of {}, {}%)".format(
        'OK' if ratio > args.match_threshold else 'FAILURE', matching, total, int(ratio * 100)
    )

    # Check random documents
    # Since the previous scan only checks a subset of documents, this is meant to be a random search
    # trying to spot checks on whether or not data was moved over correctly.

    current_checked = 0
    matching = 0
    current_offset = -1
    while float(current_checked) / new_count < args.check_percentage:
        # We only want to page a certain amount before regenerating a new set of
        # random documents.
        if current_offset > RANDOM_CHECKS_BEFORE_RESET or current_offset < 0:
            seed = random.randint(0, 1000)
            current_offset = 0
            body = {
                'size': RANDOM_CHECK_SIZE,
                'from': current_offset,
                'query': {
                    'function_score': {
                        'functions': [{
                            'random_score': {
                                'seed': seed
                            }
                        }]
                    }
                }
            }
        results = old_es.search(
            index=old_index, body=body
        )
        ids = [{'_id': elt['_id']} for elt in results['hits']['hits']]
        matching += find_matching_ids(new_es, new_index, ids)
        num_elts = len(ids)
        current_checked += num_elts
        current_offset += num_elts

        if current_checked % 100 == 0:
            print 'processed {} items'.format(current_checked)

    ratio = float(matching) / current_checked
    print "{}: random documents matching ({} out of {}, {}%)".format(
        'OK' if ratio > args.match_threshold else 'FAILURE', matching, current_checked, int(ratio * 100)
    )


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

if __name__ == '__main__':
    main()
