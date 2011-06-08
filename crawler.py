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
    -d, --dump      : Dump received chunk data (see Dump)
    --help          : Print this help message

Dump:
    a, all          : Dump all received chunk data
    e, error        : Dump only chunk data which contains errors
    n, none         : Dump nothing (default)

'''

import getopt
import sys
import signal
import logging
import re
from httpasync.HTTPAsyncClient import HTTPAsyncClient
from httpasync.HTTPCrawler import HTTPCrawler
from collections import deque
from math import ceil
import tempfile


THREADS = []

log = logging.getLogger()
if not log.handlers:
    handler = logging.StreamHandler(sys.stdout)
    frm = logging.Formatter("%(asctime)s %(levelname)s: %(threadName)s "
        "%(message)s", "%d.%m.%Y %H:%M:%S")
    handler.setFormatter(frm)
    log.addHandler(handler)


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
        self._log.info("%s %s %7.3f %s" %
                (self._status, result, self._time, self._path))


class DumpClient(WikiClient):
    """A special instance, which dumps the body into the tmp directory."""

    def process_response(self, header, chunk):
        """Dump chunk into tmp directory."""
        WikiClient.process_response(self, header, chunk)
        tmp = tempfile.NamedTemporaryFile(prefix="wikicrawler_", delete=False)
        tmp.write(chunk.split("\r\n")[1])
        tmp.close()
        self._log.debug("Chunk from %s dumped to %s" % (self._path, tmp.name))


class DumpErrorClient(DumpClient):
    """Dump data chunk only on existing errors."""

    def process_response(self, header, chunk):
        """Dump chunk into tmp directory if it contains errors."""
        if WikiClient.PATTERN_ERROR.search(chunk):
            DumpClient.process_response(self, header, chunk)
        else:
            WikiClient.process_response(self, header, chunk)


class WikiCrawler(HTTPCrawler):
    """
    A wikipedia instance of HTTPCrawler.

    Uses instances of WikiClient as client.

    """

    def __init__(self, host, paths, port=80, async=4, loglevel=10, retry=7,
            dump=None):
        HTTPCrawler.__init__(self, host, paths, port, async, loglevel, retry)
        self._dump = dump

    def create_client(self, host, paths, port, channels, loglevel):
        if self._dump is None:
            return WikiClient(host, paths, port, channels, loglevel)
        elif self._dump == "all":
            return DumpClient(host, paths, port, channels, loglevel)
        elif self._dump == "error":
            return DumpErrorClient(host, paths, port, channels, loglevel)
        else:
            self._log.error("Unknown dump level")
            sys.exit(1)


def main():
    """Start crawler with sys.args"""
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h:p:f:s:c:t:a:l:d:",
                ["host=", "port=", "file=", "start=", "count=",
                    "threads=", "async=", "log=", "dump=", "help"])
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
    dump = None

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
        elif o in ("-d", "--dump"):
            if a in ("n", "none"):
                dump = None
            elif a in ("e", "error"):
                dump = "error"
            elif a in ("a", "all"):
                dump = "all"
            else:
                print >> sys.stderr, "Unknown dump level"
                sys.exit(1)

    log.setLevel(loglevel)

    # get paths
    paths = deque(readpaths(pathfile, start, count))

    min_threads = min(threads, int(ceil(len(paths) / float(async))))
    if min_threads < threads:
        log.debug("Needless threads requested. Thread number reduced to %d." %
                min_threads)

    for i in xrange(0, min_threads):
        thread = WikiCrawler(host, paths, port, async, dump=dump)
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
    log.debug("Caught signale")
    log.debug("Stop threads")
    for thread in THREADS:
        thread.terminate()
    sys.exit(1)

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, terminate)
    main()
