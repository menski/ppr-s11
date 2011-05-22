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
import logging
import re


class HTTPAsyncClient(asynchat.async_chat):
    """
    A HTTP client which request a list of paths from a given host.
    The client uses asynchronous requests and HTTP/1.1 persistent connections.

    """

    HTTP_COMMAND = "GET %s HTTP/1.1\r\nHost: %s\r\n\r\n"
    CONNECTION = re.compile("^Connection:.*$", re.MULTILINE)

    def __init__(self, host, paths, port=80, map=None, loglevel=10):
        """
        HTTPAsyncClient is an asynchronous HTTP/1.1 client.

        This client sends asynchronous HTTP/1.1 requests with persistent
        connections.

        Arguments:
        - `host`     : host adress
        - `paths`    : deque with paths to request
        - `port`     : port number
        - `map`      : dict for asyncore.loop
        - `loglevel` : numeric log level
        """

        asynchat.async_chat.__init__(self, map=map)

        self._host = host
        self._paths = paths
        self._port = port
        self._path = ""
        self._data = ""
        self._header = ""

        self.set_terminator("\r\n\r\n")

        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((self._host, self._port))

        formatter = logging.Formatter(
                "%%(asctime)s %%(levelname)s: %%(threadName)s FD:%(fileno)3d "
                "%%(message)s" % {"fileno": self.fileno()},
                "%d.%m.%Y %H:%M:%S")
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)

        self._log = logging.getLogger(__name__ + "_FD%d" % self.fileno())
        self._log.addHandler(handler)
        self._log.setLevel(loglevel)
        self._log.debug("HTTPAsyncClient connected to %s:%s" %
                (self._host, self._port))

        self.next_path()

    def next_path(self):
        """Push next request to host."""
        self._path = ""
        try:
            self._path = self._paths.popleft()
            request = self.HTTP_COMMAND % (self._path, self._host)
            self.push(request)
            self._log.debug("Send request: %s" %
                    request.replace("\r\n", "(CRLF)"))
        except IndexError:
            self.close()

    def handle_connect(self):
        """Handle a successful connection."""
        pass

    def handle_close(self):
        """Handle connection close."""
        self.close()

    def handle_expt(self):
        """Handle exception."""
        self.close()

    def collect_incoming_data(self, data):
        """Receive a chunk of incoming data."""
        self._data += data

    def found_terminator(self):
        """Handle a found terminator."""
        if not self._header:
            self._header = self._data
            m = self.CONNECTION.search(self._header)
            con = ""
            if m is not None:
                con = ", %s" % m.group(0)
            self._log.debug("Header received (Status: %s%s)" %
                    (self.get_status(self._header), con))
        else:
            self.process_response(self._header, self._data)
            self._header = ""
            self.next_path()
        self._data = ""

    def process_response(self, header, chunk):
        """Process a response header and received chunk."""
        self._log.debug("Received response (Status: %s, Length: %d)" %
                (self.get_status(header), len(self.get_body(chunk))))

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
        return chunk.split("\r\n")[1]
