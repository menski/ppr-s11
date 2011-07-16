'''
File: http.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Basic http classes for http requests.
'''
from basic import PipeReader
import asynchat
import asyncore
import socket
import re
import time
import os
import urllib
import multiprocessing
import os.path


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

    def __init__(self, host, pipe, port=80, channels=None):
        if not pipe.poll():
            return
        asynchat.async_chat.__init__(self, map=channels)
        self._log = multiprocessing.get_logger()
        self._host = host
        self._pipe = pipe
        self._port = port
        self._time = 0
        self.set_terminator(HTTPAsyncClient.TERMINATOR)
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.connect((self._host, self._port))
        self._log.debug(self.logmsg("HTTPAsyncClient connected to %s:%d" %
            (self._host, self._port)))
        self.send_request()

    def logmsg(self, msg):
        return "[FD: %3d] %s" % (self.fileno(), msg)

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

        if self._pipe.poll():
            self._path = self._pipe.recv()
            if self._path is None:
                self._log.debug(self.logmsg("Done message found"))
                self.close()
            else:
                request = self.get_request()
                self.push(request)
                self._time = time.time()
                self._log.info(self.logmsg("Send request: %s" %
                    request.replace("\r\n", "(CRLF)")))
        else:
            self._log.debug("Close connection (no requests found)")
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
            "Header received (Protocol: %s, Status: %d %s, Close: %s, Chunk: "
            "%s, Content-Lenght: %d, Time: %f) %s" % (self._protocol,
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
            "Response received (Protocol: %s, Status: %d %s, Length: %d, "
            "Time: %f) %s" % (self._protocol, self._status, self._status_msg,
            len(self._body), self._time, self._path)))


class HTTPCrawler(PipeReader):
    """docstring for HTTPCrawler"""

    def __init__(self, host, port=80, async=100, retry=7,
            timeout=PipeReader.DEFAULT_TIMEOUT):
        PipeReader.__init__(self, timeout)
        self._host = host
        self._port = port
        self._async = async
        self._retry = retry
        self._clients = []
        self._done = False
        self._channels = dict()
        self._log.debug("HTTPCrawler created for %s:%d with %d clients" %
                (self._host, self._port, self._async))

    def create_client(self):
        return HTTPAsyncClient(self._host, self._pipe, self._port,
                self._channels)

    def postprocess(self):
        for client in self._clients:
            path = client.get_path()
            if path is None:
                self._done = True
                self._log.debug("Done message found")
                break
            else:
                if path:
                    self.pipe.send(path)

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
                while self._pipe.poll(self._timeout):
                    self._channels.clear()
                    self._clients = [self.create_client() for i in
                        range(self._async)]

                    asyncore.loop(map=self._channels)
                    self.postprocess()
                    if self._done:
                        break
                else:
                    self._log.error("Poll timeout (close pipe)")
                    self._done = True
                    break
        else:
            self._log.error("Unable to connect to %s:%d" %
                    (self._host, self._port))


class FileClient(HTTPAsyncClient):

    def __init__(self, host, pipe, directory, port=80, channels=None):
        HTTPAsyncClient.__init__(self, host, pipe, port, channels)
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

    def __init__(self, host, directory, port=80,
            async=25, retry=7, timeout=PipeReader.DEFAULT_TIMEOUT):
        HTTPCrawler.__init__(self, host, port, async, retry, timeout)
        self._dir = os.path.abspath(directory)
        self._error = set()

    def create_client(self):
        return FileClient(self._host, self._pipe, self._dir, self._port,
                self._channels)

    def postprocess(self):
        for client in self._clients:
            self._error.update(client.error())
        HTTPCrawler.postprocess(self)

    def error(self):
        return self._error()
