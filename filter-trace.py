#!/usr/bin/env python
'''
File: filter-trace.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com
Description: Filter wikipedia traces from wikibench.eu.

Usage: filter-trace.py [OPTIONS]

Options:
  -i, --interval=START:[END|SIZE]   : Interval to filter. START denotes the
                                      start unix time stamp. END denotes the
                                      end unix timestamp (including) or SIZE
                                      denotes the interval size in minutes.
                                      (required)
  -f, --file                        : Tracefile to parse. (required)
  -r, --regex                       : Regex to filter lines.
  -z, --gzip                        : Enable gzip compression for file input
                                      and output. (recommend)
  -a, --analyze                     : Analyze filtered tracefile.
  -p, --plot                        : Plot analyzed filtered tracefile 
                                      statistics. Whitout -a option ignored.
  -w, --write                       : Write page, image and thumb list files.
                                      Without -a option ignored.
  -h, --help                        : Print this help message
'''

import sys
import os.path
import getopt
import gzip
import httpasync.trace

URL_REGEX = r'|'.join([r'http://en.wikipedia.org',
    r'http://upload.wikimedia.org/wikipedia/commons/',
    r'http://upload.wikimedia.org/wikipedia/en/'])


def main():
    """Start trace filter with sys.args."""
    try:
        opts, args = getopt.getopt(sys.argv[1:], "i:hr:f:zapw",
                ["interval=", "help", "file=", "gzip", "regex=", "analyze",
                 "plot", "write"])
    except getopt.GetoptError, e:
        print >> sys.stderr, e
        print __doc__
        sys.exit(2)

    # defaults
    interval = None
    interval = (1194892290, 1194894090)
    tracefile = None
    openfunc = open
    regex = URL_REGEX
    analyze = False
    plot = False
    write = False

    # process options
    for o, a in opts:
        if o in ("-h", "--help"):
            print __doc__
            sys.exit(0)
        elif o in ("-i", "--interval"):
            try:
                (start, x) = a.split(":")
                start = float(start)
                x = float(x)
            except ValueError:
                print >> sys.stderr, "ERROR: Unable to parse interval argument"
                sys.exit(2)
            if x > start:
                interval = (start, x)
            else:
                interval = (start, start + x * 60)
        elif o in ("-f", "--file"):
            if os.path.isfile(a):
                tracefile = a
            else:
                print >> sys.stderr, "ERROR: Given tracefile does not exist"
                print __doc__
                sys.exit(2)
        elif o in ("-z", "--gzip"):
            openfunc = gzip.open
        elif o in ("-r", "--regex"):
            regex = a
        elif o in ("-a", "--analyze"):
            analyze = True
        elif o in ("-p", "--plot"):
            plot = True
        elif o in ("-w", "--write"):
            write = True

    if interval is None:
        print >> sys.stderr, "ERROR: No interval given"
        print __doc__
        sys.exit(2)

    if tracefile is None:
        print >> sys.stderr, "ERROR: No tracefile given"
        print __doc__
        sys.exit(2)

    filter = httpasync.trace.WikiFilter(tracefile, interval, regex, 
            openfunc=openfunc)

    if analyze:
        httpasync.trace.WikiAnalyzer(filter.get_filename(), openfunc, plot, 
                write)


if __name__ == '__main__':
    main()
