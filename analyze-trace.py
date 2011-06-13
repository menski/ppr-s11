#!/usr/bin/env python
'''
File: analyze-trace.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Analyze a wikipedia trace from wikibench.eu.

Usage: analyze-trace.py [OPTIONS]

Options:
    -f, --file      : Path to tracefile. (required)
    -p, --plot      : Plot results with gnuplot.
    -w, --write     : Write page, image, thumb list.
    -z, --gzip      : Read gzip compressed files.
    -h, --help      : Print this help message.

'''

import sys
import os.path
import getopt
import gzip
import httpasync.trace


def main():
    """Start analyzer with sys.argv"""
    try:
        opts, args = getopt.getopt(sys.argv[1:], "f:pzhw",
                ["file=", "plot", "gzip", "help", "write"])
    except getopt.GetoptError, e:
        print >> sys.stderr, e
        print __doc__
        sys.exit(2)

    # defaults
    tracefile = None
    plot = False
    openfunc = open
    write = False

    # process options
    for o, a in opts:
        if o in ("-h", "--help"):
            print __doc__
            sys.exit(0)
        if o in ("-f", "--file"):
            if os.path.isfile(a):
                tracefile = a
            else:
                print >> sys.stderr, "ERROR: Unable to read tracefile"
                print __doc__
                sys.exit(2)
        if o in ("-p", "--plot"):
            plot = True
        if o in ("-z", "--gzip"):
            openfunc = gzip.open
        if o in ("-w", "--write"):
            write = True

    if tracefile is None:
        print >> sys.stderr, "ERROR: Tracefile required"
        print __doc__
        sys.exit(2)

    # start analyzer
    httpasync.trace.WikiAnalyzer(tracefile, openfunc, plot, write)


if __name__ == '__main__':
    main()
