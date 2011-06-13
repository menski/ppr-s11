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
  -h, --help                        : Print this help message
'''

import sys
import os.path
import getopt
import gzip
import httpasync.trace

WIKI_REGEX = r'http://en.wikipedia.org'
UPLOAD_REGEX = r'|'.join(['http://upload.wikimedia.org/wikipedia/commons/',
        'http://upload.wikimedia.org/wikipedia/en/'
        ])
THUMB_REGEX = r'|'.join([url+'thumb/' for url in UPLOAD_REGEX.split('|')])
URL_REGEX = r'|'.join([WIKI_REGEX, UPLOAD_REGEX])

def filter_trace(tracefile, interval, openfunc=open):
    """Filter tracefile and save it in file."""

    (path, ext) = os.path.splitext(tracefile)
    outputfile = "%s.%d-%d%s" % (path, interval[0], interval[1], ext)
    pagefile = "%s.%d-%d.page%s" % (path, interval[0], interval[1], ext)
    imgfile = "%s.%d-%d.img%s" % (path, interval[0], interval[1], ext)
    thumbfile = "%s.%d-%d.thumb%s" % (path, interval[0], interval[1], ext)

    with openfunc(outputfile, mode="wb") as ofile,\
            openfunc(pagefile, mode="wb") as pfile,\
            openfunc(imgfile, mode="wb") as ifile,\
            openfunc(thumbfile, mode="wb") as tfile,\
            openfunc(tracefile) as f:
                for line in f:
                    line = line.split(" ")
                    timestamp = float(line[1])
                    url = line[2]
                    if timestamp >= interval[0] and\
                        timestamp < interval[1] + 1 and\
                        PATTERN.match(url) is not None:
                        line = "%f %s\n" % (timestamp, url)
                        ofile.write(line)
                        line = "%s\n" % timestamp
                        if IMG.match(url) is not None:
                            if THUMB.search(url) is not None:
                                tfile.write(line)
                            else:
                                ifile.write(line)
                        else:
                            pfile.write(line)


def main():
    """Start trace filter with sys.args."""
    try:
        opts, args = getopt.getopt(sys.argv[1:], "i:hr:f:zap",
                ["interval=", "help", "file=", "gzip", "regex=", "analyze",
                 "plot"])
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

    # process options
    for o, a in opts:
        if o in ("-h", "--help"):
            print __doc__
            sys.exit(0)
        elif o in ("-i", "--interval"):
            try:
                (start, x) = a.split(":")
                start = int(start)
                x = int(x)
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
        httpasync.trace.WikiAnalyzer(filter.get_filename(), openfunc, plot)


if __name__ == '__main__':
    main()
