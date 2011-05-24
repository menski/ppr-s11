#!/usr/bin/env python
'''
File: lib.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: A library for http and mysql requests.
'''

import sys
import socket
import asyncore
import asynchat
import threading
import logging
import re
import time


class HTTPAsyncClient(asynchat.async_chat):
    """
    A HTTP client which request a list of paths from a given host.
    The client uses asynchronous requests and HTTP/1.1 persistent connections.

    """

    HTTP_COMMAND = "GET %s HTTP/1.1\r\nHost: %s\r\n\r\n"
    PATTERN_CONNECTION_CLOSE = re.compile(
            r'^Connection:[ ]*(\w+).*$', re.MULTILINE)
    PATTERN_TRANSFER_ENCODING = re.compile(
            r'^Transfer-Encoding:[ ]*(\w+).*$', re.MULTILINE)
    PATTERN_CONTENT_LENGTH = re.compile(
            r'^Content-Length:[ ]*([0-9]+).*$', re.MULTILINE)

    def __init__(self, host, paths, port=80, channels=None, loglevel=10):
        """
        HTTPAsyncClient is an asynchronous HTTP/1.1 client.

        This client sends asynchronous HTTP/1.1 requests with persistent
        connections.

        Arguments:
        - `host`     : host address
        - `paths`    : deque with paths to request
        - `port`     : port number
        - `channels` : dict for asyncore.loop
        - `loglevel` : numeric log level

        """

        asynchat.async_chat.__init__(self, map=channels)

        self._host = host
        self._paths = paths
        self._port = port
        self._time = 0

        self.set_terminator("\r\n\r\n")

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((self._host, self._port))

        # TODO: improve logging
        formatter = logging.Formatter(
                "%%(asctime)s %%(levelname)s: %%(threadName)s FD:%(fileno)3d "
                "%%(message)s" % {"fileno": self.fileno()},
                "%d.%m.%Y %H:%M:%S")
        self._handler = logging.StreamHandler(sys.stdout)
        self._handler.setFormatter(formatter)

        self._log = logging.getLogger(__name__ + "_FD%d" % self.fileno())
        self._log.addHandler(self._handler)
        self._log.setLevel(loglevel)
        self._log.debug("HTTPAsyncClient connected to %s:%d" %
                (self._host, self._port))

        self.next_path()

    def clean_up(self):
        """Remove and close logging handler"""
        self._log.removeHandler(self._handler)
        self._handler.close()
        self.close()

    def next_path(self):
        """Push next request to host."""
        self._path = ""
        self._header = ""
        self._data = ""
        self._status = ""
        self._encoding = ""
        if self.get_terminator() is None:
            self.set_terminator("\r\n\r\n")
            self._log.debug("Set terminator back to '(CRLF)(CRLF)'.")
        try:
            self._path = self._paths.popleft()
            request = self.HTTP_COMMAND % (self._path, self._host)
            self.push(request)
            self._time = time.clock()
            self._log.debug("Send request: %s" %
                    request.replace("\r\n", "(CRLF)"))
        except IndexError:
            self.clean_up()

    def handle_connect(self):
        """Handle a successful connection."""
        pass

    def handle_close(self):
        """Handle connection close."""
        self.clean_up()

    def handle_error(self):
        """Handle connection error."""
        self.clean_up()

    def collect_incoming_data(self, data):
        """Receive a chunk of incoming data."""
        self._data += data
        if self.get_terminator() is None:
            self.found_terminator()

    def found_terminator(self):
        """Handle a found terminator."""
        if not self._header:
            self._header = self._data
            self._data = ""
            self._status = self.get_status(self._header)
            self._connection = self.search_pattern(
                    self.PATTERN_CONNECTION_CLOSE, self._header, prefix=", ")
            self._encoding = self.search_pattern(
                    self.PATTERN_TRANSFER_ENCODING, self._header, prefix=", ")
            self._content_length = self.search_pattern(
                    self.PATTERN_CONTENT_LENGTH, self._header, prefix=", ")
            self._log.debug("Header received (Status: %s%s%s%s)" %
                    (self._status, self._connection, self._encoding,
                    self._content_length))

            try:
                if self.search_pattern(self.PATTERN_CONTENT_LENGTH,
                        self._header, group=1) == "0":
                    self.found_terminator()
                    return
            except:
                pass

            if self.search_pattern(self.PATTERN_TRANSFER_ENCODING,
                    self._header, group=1) != "chunked":
                self.set_terminator(None)
                self._log.debug("No chunked encoding found. "
                    "Set terminator to 'None'.")
        else:
            self._time = time.clock() - self._time
            self.process_response(self._header, self._data)
            self._header = ""
            self._path = ""
            if self._connection:
                self.clean_up()
            else:
                self.next_path()

    def process_response(self, header, chunk):
        """Process a response header and received chunk."""
        self._log.debug(
                "Response received (Status: %s, Length: %d, Time: %f)" %
                (self.get_status(header), len(self.get_body(chunk)),
                self._time))

    def unfinished_path(self):
        """Return path if the request was aborted."""
        return self._path

    @staticmethod
    def get_status(header):
        """Split header and return response status code."""
        return header.split("\r\n", 1)[0].split(" ")[1]

    @staticmethod
    def get_body(chunk):
        """Split chunk and return HTML body."""
        try:
            return chunk.split("\r\n")[1]
        except IndexError:
            return chunk

    @staticmethod
    def search_pattern(pattern, string, group=0, prefix="", suffix=""):
        """Search for pattern in string"""
        result = ""
        m = pattern.search(string)
        if m is not None:
            result = "".join([prefix, m.group(group).strip(), suffix])
        return result


class HTTPCrawler(threading.Thread):
    """
    A HTTP crawler which uses asynchronous requests.
    A given list of paths are request from a host by using instances
    of the HTTPAsyncClient class.

    """

    def __init__(self, host, paths, port=80, async=4, loglevel=10):
        """
        HTTPCrawler is a HTTP/1.1 crawler, using HTTPAsyncClient.

        The crawler requests a list of paths from a given host. To request
        the paths from the host, instances of HTTPAsyncClient are used.

        Arguments:
        - `host`     : host address
        - `paths`    : deque of paths to request
        - `port`     : port number
        - `async`    : number of asynchronous requests
        - `loglevel` : numeric log level

        """
        threading.Thread.__init__(self)
        self._host = host
        self._paths = paths
        self._port = port
        self._async = async
        self._loglevel = loglevel
        self._clients = []
        self._channels = dict()
        self._terminate = False

        formatter = logging.Formatter(
                "%(asctime)s %(levelname)s: %(threadName)s %(message)s",
                "%d.%m.%Y %H:%M:%S")
        self._handler = logging.StreamHandler(sys.stdout)
        self._handler.setFormatter(formatter)

        self._log = logging.getLogger(__name__ + "_%s" % str(self))
        self._log.addHandler(self._handler)
        self._log.setLevel(loglevel)
        self._log.debug("HTTPCrawler created for %s:%d with %d clients" %
                (self._host, self._port, self._async))

    def create_client(self, host, paths, port, channels, loglevel):
        return HTTPAsyncClient(host, paths, port, channels, loglevel)

    def run(self):
        """Run the HTTPCrawler thread."""

        # Test connection
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self._host, self._port))
        except socket.error, e:
            self._log.error("Unable to connect to %s:%d (%s)" %
                    (self._host, self._port, e))
            return
        finally:
            s.close()

        while not self._terminate and self._paths:
            self._channels.clear()
            self._clients[:]
            self._clients = [self.create_client(self._host, self._paths,
                self._port, self._channels, self._loglevel)
                for i in xrange(0, self._async)]

            # start asynchronous requests
            asyncore.loop(map=self._channels)

            # find abortet request paths
            for client in self._clients:
                if client.unfinished_path():
                    self._paths.append(client.unfinished_path())
        self.clean_up()

    def clean_up(self):
        """Remove and close logging handler"""
        self._log.removeHandler(self._handler)
        self._handler.close()

    def terminate(self):
        """Terminate the crawler and his clients."""
        self._log.debug("Terminate crawler %s" % self)
        self._terminate = True
        for client in self._clients:
            client.close()
        self.clean_up()
