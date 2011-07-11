'''
File: basic.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Basic classes for project.
'''

import sys
import logging
import multiprocessing
import Queue
import asynchat
import asyncore
import socket
import re
import time
import os
import urllib


class Process(multiprocessing.Process):
    """ Basic process class. """

    def __init__(self, output=sys.stdout, loglevel=logging.DEBUG):
        multiprocessing.Process.__init__(self)
        self._log = multiprocessing.get_logger()
        if not self._log.handlers:
            self.create_log_handler(output, loglevel)
        self._log.debug("Process created %s" % self.name)

    def create_log_handler(self, output, loglevel):
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)8s: %(processName)s %(threadName)s "
            "%(message)s", "%d.%m.%Y %H:%M:%S")
        handler = logging.StreamHandler(output)
        handler.setFormatter(formatter)
        self._log.addHandler(handler)
        self.set_log_level(loglevel)
        self._log.debug("New handler added to logger")

    def set_log_level(self, loglevel):
        if self._log.level != loglevel:
            self._log.setLevel(loglevel)
            self._log.debug("Set log level to: %d" % loglevel)

    def run(self):
        self._log.debug("Running")


class FileReader(Process):
    """ Basic file reader process. """

    def __init__(self, openfunc=open, processfunc=None):
        Process.__init__(self)
        self._openfunc = openfunc
        self._processfunc = processfunc
        self._filenames = []

    def read(self, filename):
        self._filenames.append(filename)

    def run(self):
        if self._processfunc is None:
            self._log.error("No processing function given")
            return

        if self._filenames:
            for filename in self._filenames:
                try:
                    self._log.debug("Read file %s" % filename)
                    input = self._openfunc(filename, "r")
                    try:
                        for line in input:
                            self._processfunc(line.strip())
                    finally:
                        input.close()
                except IOError, e:
                    self._log.error(e)
        else:
            self._log.warning("No files given")


class FileWriter(Process):
    """ Basic file writer process. """

    DONE = "###DONE###"

    def __init__(self, filename, queue=multiprocessing.Queue(), openfunc=open):
        Process.__init__(self)
        self._filename = filename
        self._openfunc = openfunc
        self._queue = queue
        self._done = False

    def write(self, line):
        self._queue.put(line + "\n")

    def done(self):
        self._queue.put(FileWriter.DONE)

    def run(self):
        try:
            output = self._openfunc(self._filename, "w")
            self._log.debug("Write file %s", self._filename)
            try:
                while not self._done or not self._queue.empty():
                    try:
                        line = self._queue.get(timeout=1)
                        if line == FileWriter.DONE:
                            self._done = True
                            self._log.debug("Found done message")
                        else:
                            output.write(line)
                    except Queue.Empty:
                        pass
            finally:
                output.close()
        except IOError, e:
            self._log.error(e)


class HTTPAsyncClient(asynchat.async_chat):
    """docstring for HTTPAsyncClient"""

    TERMINATOR = "\r\n\r\n"
    HTTP_COMMAND = "GET %s HTTP/1.1\r\nHost: %s\r\n\r\n"
    PATTERN_CONNECTION_CLOSE = re.compile(
            r'^Connection:[ ]*(\w+).*$', re.MULTILINE)
    PATTERN_TRANSFER_ENCODING = re.compile(
            r'^Transfer-Encoding:[ ]*(\w+).*$', re.MULTILINE)
    PATTERN_CONTENT_LENGTH = re.compile(
            r'^Content-Length:[ ]*([0-9]+).*$', re.MULTILINE)

    def __init__(self, host, queue, port=80, channels=None):
        asynchat.async_chat.__init__(self, map=channels)
        self._log = multiprocessing.get_logger()
        self._host = host
        self._queue = queue
        self._port = port
        self._time = 0
        self.set_terminator(HTTPAsyncClient.TERMINATOR)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((self._host, self._port))
        self._log.debug(self.logmsg("HTTPAsyncClient connected to %s:%d" %
            (self._host, self._port)))
        self.send_request()

    def logmsg(self, msg):
        return "FD: %3d %s" % (self.fileno(), msg)

    def get_request(self):
        return HTTPAsyncClient.HTTP_COMMAND % (self._path, self._host)

    def send_request(self):
        self._path = ""
        self._header = ""
        self._body = ""
        self._data = ""
        self._protocol = ""
        self._status = -1
        self._status_msg = ""
        self._close = False
        self._chunked = True
        self._content_length = -1

        try:
            self._path = self._queue.get(timeout=1)
            if self._path == HTTPCrawler.DONE:
                self._log.debug(self.logmsg("Done message found"))
                self.close()
            else:
                request = self.get_request()
                self.push(request)
                self._time = time.time()
                self._log.info(self.logmsg("Send request: %s" %
                    request.replace("\r\n", "(CRLF)")))
        except Queue.Empty:
            self._log.debug(self.logmsg("Queue empty => close"))
            self.close()

    def collect_incoming_data(self, data):
        self._data += data
        if not self._chunked and len(self._data) >= self._content_length:
            self.found_terminator()

    def found_terminator(self):
        if not self._header:
            self._htime = time.time() - self._time
            self._header = self._data
            self._data = ""
            self.analyze_header()

            if self._content_length == 0:
                self.found_terminator()
        else:
            self._time = time.time() - self._time
            self._body = self._data
            self.process_response()
            self._path = ""
            if self._close:
                self.close()
            else:
                self.send_request()

    def analyze_header(self):
        self._protocol, self._status, self._status_msg = self._header.split(
                "\r\n")[0].split(" ", 2)
        self._status = int(self._status)
        self._close = self.get_close()
        self._chunked = self.get_chunked()
        self._content_length = self.get_content_length()
        self._log.info(self.logmsg(
            "Header received (Protocol: %s Status: %d %s Close: %s Chunk: %s "
            "Content-Lenght: %d Time: %f) %s" % (self._protocol,
                self._status, self._status_msg, self._close, self._chunked, 
                self._content_length, self._htime, self._path)))

    def get_status(self):
        return -1

    def get_close(self):
        m = HTTPAsyncClient.PATTERN_CONNECTION_CLOSE.search(self._header)
        return m is not None

    def get_chunked(self):
        m = HTTPAsyncClient.PATTERN_TRANSFER_ENCODING.search(self._header)
        return m is not None

    def get_content_length(self):
        m = HTTPAsyncClient.PATTERN_CONTENT_LENGTH.search(self._header)
        if m is not None:
            return int(m.group(1))
        else:
            return -1

    def get_path(self):
        return self._path

    def process_response(self):
        self._log.info(self.logmsg(
            "Response received (Protocol: %s Status: %d %s Length: %d, Time: "
            "%f) %s" % (self._protocol, self._status, self._status_msg,
            len(self._body), self._time, self._path)))


class HTTPCrawler(Process):
    """docstring for HTTPCrawler"""

    DONE = "###DONE###"

    def __init__(self, host, queue, port=80, async=10, retry=7):
        Process.__init__(self)
        self._host = host
        self._queue = queue
        self._port = port
        self._async = async
        self._retry = retry
        self._clients = []
        self._channels = dict()
        self._done = False
        self._log.debug("HTTPCrawler created for %s:%d with %d clients" %
                (self._host, self._port, self._async))

    def create_client(self):
        return HTTPAsyncClient(self._host, self._queue, self._port,
                self._channels)

    def postprocess(self):
        for client in self._clients:
            path = client.get_path()
            if path:
                if path == HTTPCrawler.DONE:
                    self._done = True
                    self._log.debug("Done message found")
                    break
                else:
                    self._queue.put(path)

    def test_connection(self):
        while self._retry > 0:
            self._retry -= 1
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((self._host, self._port))
            except socket.gaierror, e:
                self._log.error(e)
                return False
            except socket.error, e:
                self._log.error(e)
            except Exception, e:
                self._log.error(e)
                return False
            else:
                return True
            finally:
                s.close()
        return False

    def run(self):
        if self.test_connection():
            while not self._done:
                self._channels.clear()
                self._clients = [self.create_client() for i in 
                        range(self._async)]

                asyncore.loop(map=self._channels)
                self.postprocess()
        else:
            self._log.error("Unable to connect to %s:%d" %
                    (self._host, self._port))


class FileClient(HTTPAsyncClient):

    def __init__(self, host, queue, directory, port=80, channels=None):
        HTTPAsyncClient.__init__(self, host, queue, port, channels)
        self._dir = directory
        self._error = set()

    def process_response(self):
        HTTPAsyncClient.process_response(self)
        if self._status == 200:
            file_path = re.sub(r'^/[\w-]+/[\w-]+/', '/', self._path)
            file_path = self._dir + urllib.unquote(file_path)
            file_path = os.path.abspath(file_path)
            directory = os.path.split(file_path)[0]
            try:
                if not os.path.isdir(directory):
                    os.makedirs(directory)
                    self._log.info(self.logmsg("Create directory %s" %
                        directory))
                with open(file_path, "wb") as output:
                    output.write(self._data)
                self._log.info(self.logmsg("Write %s to %s" %
                    (self._path, file_path)))
            except Exception, e:
                self._log.error(self.logmsg(e))
        else:
            self._error.add(self._host + self._path)

    def error(self):
        return self._error


class FileCrawler(HTTPCrawler):

    def __init__(self, host, queue, directory, port=80, async=10, retry=7):
        HTTPCrawler.__init__(self, host, queue, port, async, retry)
        self._dir = directory
        self._error = set()

    def create_client(self):
        return FileClient(self._host, self._queue, self._dir, self._port,
                self._channels)

    def postprocess(self):
        for client in self._clients:
            self._error.update(client.error())
        HTTPCrawler.postprocess(self)

    def error(self):
        return self._error()


