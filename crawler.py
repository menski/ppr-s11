#!/usr/bin/env python
'''
File: crawler.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: A HTTP crawler, which use threads to send asynchronous
             HTTP/1.1 requests.

Usage: crawler.py [OPTIONS]

Options:
    -h, --host      : Host name (default: ib1)
    -p, --port      : Port number (default: 80)
    -f, --file      : Path file (default: pages.txt)
    -s, --start     : Start index (default: 0)
    -c, --count     : Number of paths to request (default: 100)
    -t, --threads   : Number of threads (default: 4)
    -a, --async     : Number of asynchronous requests (default: 10)
    -l, --log       : Log level (default: DEBUG)
    --help          : Print this message
'''

import getopt
import sys
import signal
import logging
import re
from lib import HTTPAsyncClient, HTTPCrawler
from collections import deque


THREADS = []

handler = logging.StreamHandler(sys.stderr)
frm = logging.Formatter("%(asctime)s %(levelname)s: %(message)s",
                              "%d.%m.%Y %H:%M:%S")
handler.setFormatter(frm)

log = logging.getLogger("crawler")
log.addHandler(handler)
log.setLevel(logging.DEBUG)


class WikiClient(HTTPAsyncClient):
    """
    A wikipedia instance of HTTPAsyncClient.

    Special regex matching on response body.

    """

    PATTERN_SERVED = re.compile(
            r'Served[ ]*by[ ]*(\w+)[ ]*in[ ]*([0-9]*\.[0-9]*)[ ]*secs')
    PATTERN_ERROR = re.compile(r'MediaTransformError')

    def process_response(self, header, chunk):
        """Search for served by SERVER in SECONDS and errors."""
        HTTPAsyncClient.process_response(self, header, chunk)
        match = self.PATTERN_SERVED.search(chunk)
        result = ""
        if match is not None:
            result = "%s %7.3f" % (match.group(1), float(match.group(2)))
        errors = self.PATTERN_ERROR.findall(chunk)
        if errors:
            error_count = len(errors)
        else:
            error_count = 0

        result = "%s Errors: %2d" % (result, error_count)
        self._log.info("%s %s %s" % (self._status, result, self._path))


class WikiCrawler(HTTPCrawler):
    """
    A wikipedia instance of HTTPCrawler.

    Uses instances of WikiClient as client.

    """

    def create_client(self, host, paths, port, channels, loglevel):
        return WikiClient(host, paths, port, channels, loglevel)


def main():
    """Start crawler with sys.args"""
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h:p:f:s:c:t:a:l:",
                ["host=", "port=", "file=", "start=", "count=",
                    "threads=", "async=", "log=", "help"])
    except getopt.GetoptError, e:
        print >> sys.stderr, e
        print __doc__
        sys.exit(2)

    # defaults
    host = "ib1"
    port = 80
    pathfile = "pages.txt"
    start = 0
    count = 100
    threads = 4
    async = 10
    loglevel = 10

    # process options
    for o, a in opts:
        if o == "--help":
            print __doc__
            sys.exit(0)
        elif o in ("-h", "--host"):
            host = a
        elif o in ("-p", "--port"):
            try:
                port = int(a)
            except ValueError, e:
                print >> sys.stderr, "Port argument must be a number"
                sys.exit(1)
        elif o in ("-f", "--file"):
            pathfile = a
        elif o in ("-s", "--start"):
            try:
                start = int(a)
                if start < 0:
                    print >> sys.stderr, "Start index must be positiv"
                    sys.exit(2)
            except ValueError, e:
                print >> sys.stderr, "Start index must be a number"
                sys.exit(2)
        elif o in ("-c", "--count"):
            try:
                count = int(a)
                if count < 1:
                    print >> sys.stderr, "Path count must be greater 0"
                    sys.exit(2)
            except ValueError, e:
                print >> sys.stderr, "Path count must be a number"
                sys.exit(2)
        elif o in ("-t", "--threads"):
            try:
                threads = int(a)
                if threads < 1:
                    print >> sys.stderr, "Thread count must be greater 0"
                    sys.exit(2)
            except ValueError, e:
                print >> sys.stderr, "Thread count must be a number"
                sys.exit(2)
        elif o in ("-a", "--async"):
            try:
                async = int(a)
                if async < 1:
                    print >> sys.stderr, "Async count must be greater 0"
                    sys.exit(2)
            except ValueError, e:
                print >> sys.stderr, "Async count must be a number"
                sys.exit(2)
        elif o in ("-l", "--log"):
            loglevel = getattr(logging, a.upper(), None)
            if loglevel is None:
                print >> sys.stderr, "Log level is not valid"
                sys.exit(2)

    # get paths
    paths = deque(readpaths(pathfile, start, count))

    for i in xrange(0, threads):
        thread = HTTPCrawler(host, paths, port, async)
        thread.start()
        THREADS.append(thread)

    while THREADS:
        for thread in THREADS:
            try:
                thread.join(1)
            except KeyboardInterrupt:
                terminate(2, None)
            if not thread.is_alive():
                THREADS.remove(thread)


def readpaths(pathfile, start=0, count=100):
    """Read paths from a file."""
    try:
        with open(pathfile) as f:
            paths = f.readlines()[start:(start + count)]
        return [p.strip() for p in paths]
    except IOError, e:
        log.error("Unable to read paths file (%s)" % e)
        sys.exit(1)


def terminate(signum, frame):
    """Handle signals"""
    log.error("Caught signale")
    log.debug("Stop threads")
    for thread in THREADS:
        thread.terminate()
    sys.exit(1)

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, terminate)
    main()
