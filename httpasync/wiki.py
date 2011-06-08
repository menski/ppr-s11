'''
File: wiki.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Collection of clients and crawler for wikipedia.
'''

import sys
from http import HTTPAsyncClient, HTTPCrawler
import re
import tempfile


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
