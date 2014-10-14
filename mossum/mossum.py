"""
Mossum is a tool for summarizing results from Stanford's Moss. The tool
generates a graph for (multiple) results from Moss, which can help in
identifying groups of students that have shared solutions.

The tool can also generate a report, which shows which solutions are similar
between all pairs of students. When submitting multiple parts of an assignment
to Moss, this can help in identifying which students have multiple similar
solutions.
"""

import re
import sys
import os
import datetime
import pydot
import argparse
import requests as r

from bs4 import BeautifulSoup
from faker import Faker
from collections import defaultdict

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('urls', metavar='URL', nargs='*',
                   help='URLs to Moss result pages.')
parser.add_argument('--min-percent', '-p', dest='min_percent', metavar='P', type=int, default=90,
                   help='All matches where less than P%% of both files are matched are ignored. (Default: 90)')
parser.add_argument('--min-lines', '-l', dest='min_lines', metavar='L', type=int, default=1,
                   help='All matches where fewer than L lines are matched are ignored. (Default: 1)')
parser.add_argument('--format', '-f', default='png', help='Format of output files. See Graphviz documentation.')
parser.add_argument('--transformer', '-t', default='.*',
                   help='A regular expression that is used to transform the name of them matched files.')
parser.add_argument('--anonymize', '-a', default=False, action='store_true',
                   help='Substitute names of matched files for random names')
parser.add_argument('--merge', '-m', default=False, action='store_true',
                   help='Merge all reports into one image')
parser.add_argument('--report', '-r', default=False, action='store_true',
                   help='Generates a report showing how many submissions each pair has in common.')
parser.add_argument('--show-links', '-s', default=False, dest='show_links', action='store_true',
                   help='Add hyperlinks to graph edges to Moss results. Only works for the formats svg and xlib.')
parser.add_argument('--output', '-o', default=None,
                   help='Name of output file.')
parser.add_argument('--filter', metavar='N', nargs='+', default=None,
                   help='Include only matches between these names.')
parser.add_argument('--filteri', metavar='N', nargs='+', default=None,
                   help='Include only matches involving these names.')
parser.add_argument('--filterx', metavar='N', nargs='+', default=None,
                   help='Exclude matches between these names.')
parser.add_argument('--filterxi', metavar='N', nargs='+', default=None,
                   help='Exclude matches involving any of these names.')
args = None


class Results:
    def __init__(self, name, matches):
        self.name = name
        self.matches = matches


class Match:
    def __init__(self, first, second, lines, url):
        self.first = first
        self.second = second
        self.lines = lines
        self.url = url


class File:
    def __init__(self, name, percent):
        self.name = name
        self.percent = percent


class Filter:
    def __init__(self):
        filters = ['filter', 'filteri', 'filterx', 'filterxi']
        for f in filters:
            setattr(self, f, None)

        for f in filters:
            if getattr(args, f) != None:
                setattr(self, f, set(getattr(args, f)))

    def include(self, match):
        first = match.first.name
        second = match.second.name
        if (self.filter is not None and (first not in self.filter or second not
            in self.filter)):
            return False
        if (self.filteri is not None and (first not in self.filteri and second
            not in self.filteri)):
            return False
        if (self.filterx is not None and (first in self.filterx and second in
            self.filterx)):
            return False
        if (self.filterxi is not None and (first in self.filterxi or second in
            self.filterxi)):
            return False
        return match.lines > args.min_lines and (match.first.percent > args.min_percent  or
                match.second.percent > args.min_percent)


def date_str():
    return datetime.datetime.today().strftime('%d-%m-%Y_%H%M%S')


def parse_col(col):
    name, per = col.split()
    m = re.match(args.transformer, name)
    if m:
        if m.groups():
            name = '_'.join(m.groups())
        else:
            name = m.group()
    per = int(re.search(r'\d+',per).group())
    return File(name, per)


def random_names(length):
    fake = Faker()

    names = set()
    while len(names) < length:
        names.add(fake.word())

    return names


def anonymize(matches):
    s = set()
    for m in matches:
        s.add(m.first.name)
        s.add(m.second.name)

    new_names = dict(zip(s,random_names(len(s))))

    for m in matches:
        m.first.name = new_names[m.first.name]
        m.second.name = new_names[m.second.name]


def generate_report(results):
    pairs = defaultdict(list)
    for res in results:
        for match in res.matches:
            pairs[(match.first.name, match.second.name)].append( (res.name, match) )

    if args.output:
        base = args.output
    else:
        base = '+'.join(map(lambda x:x.name, results))
    filename = '%s.txt' % base

    with open(filename, 'w') as f:
        for pair, matches in sorted(pairs.items(),
                key=lambda x: (len(x[1]), sorted(map(lambda x: x[0], x[1]))), reverse=True):
            f.write('Pair: %s and %s\n' % pair)
            for name, match in sorted(matches):
                f.write('%s: %s\n' % (name, match.url))

            f.write('\n\n')


def merge_results(results):
    name = '+'.join(map(lambda x:x.name, results))
    matches = sum(map(lambda x:x.matches, results), [])
    return Results(name, matches)


def get_results(moss_url):
    resp = r.get(moss_url)
    soup = BeautifulSoup(resp.content.decode('utf-8'), 'html5lib')

    ps = soup('p')
    name = None
    if len(ps) >= 2:
        name = ps[2].text.strip()
    if not name:
        name = 'moss_%s' % date_str()

    matches = []

    for row in soup.table('tr')[1:]:
        first, second, lines = map(lambda x:x.text, row('td'))
        first = parse_col(first)
        second  = parse_col(second)
        lines = int(lines)
        url = row.a['href']
        matches.append(Match(first, second, lines, url))

    fil = Filter()
    matches = list(filter(fil.include,matches))

    return Results(name, matches)


def image(results):
    graph = pydot.Dot(graph_type='graph')

    print('Generating image for %s' % results.name)
    for m in results.matches:
        extra_opts = {}
        if args.show_links:
            extra_opts = {'label': 'M',
                    'labelURL': m.url,
                    'URL': m.url}
        graph.add_edge(pydot.Edge(m.first.name, m.second.name, **extra_opts))

    if args.output:
        name = args.output
    else:
        name = results.name
    filename = '%s.%s' % (name, args.format)

    if os.path.exists(filename):
        os.remove(filename)

    graph.write(filename, format=args.format)
    if args.format == 'xlib':
        os.remove(filename)
    print('DONE')


def main():
    global args
    args = parser.parse_args()

    urls = args.urls
    if not urls:
        urls = sys.stdin.read().splitlines()

    all_res = []
    for x in urls:
        res = get_results(x)
        all_res.append(res)


    if args.merge:
        merged = merge_results(all_res)
        if args.anonymize:
            anonymize(merged.matches)
        image(merged)
    else:
        for res in all_res:
            if args.anonymize:
                anonymize(res.matches)
            image(res)

    if args.report:
        generate_report(all_res)


if __name__ == '__main__':
    main()
