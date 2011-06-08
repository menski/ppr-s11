'''
File: HTTPCrawler.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: The HTTPCrawler class implements a asynchronous crawler which
    uses the HTTPAsyncClient class for the clients.
'''

import sys
import socket
import asyncore
import HTTPAsyncClient
import threading
import logging


class HTTPCrawler(threading.Thread):
    """
    A HTTP crawler which uses asynchronous requests.
    A given list of paths are request from a host by using instances
    of the HTTPAsyncClient class.

    """

    def __init__(self, host, paths, port=80, async=4, loglevel=10, retry=7):
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
        - `loglevel` : number of retrys

        """
        threading.Thread.__init__(self)
        self._host = host
        self._paths = paths
        self._port = port
        self._async = async
        self._loglevel = loglevel
        self._retry = retry
        self._clients = []
        self._channels = dict()
        self._terminate = False

        self._log = logging.getLogger()
        if not self._log.handlers:
            formatter = logging.Formatter(
                "%(asctime)s %(levelname)s: %(threadName)s %(message)s",
                "%d.%m.%Y %H:%M:%S")
            self._handler = logging.StreamHandler(sys.stdout)
            self._handler.setFormatter(formatter)
            self._log.addHandler(self._handler)
            self._log.setLevel(loglevel)
        self._log.debug("HTTPCrawler created for %s:%d with %d clients" %
                (self._host, self._port, self._async))

    def create_client(self, host, paths, port, channels, loglevel):
        return HTTPAsyncClient(host, paths, port, channels, loglevel)

    def run(self):
        """Run the HTTPCrawler thread."""

        # Test connection (self._retry times)
        while self._retry > 0:
            self._retry -= 1
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.connect((self._host, self._port))
            except socket.gaierror, e:
                self._log.error("Unable to connect to %s:%d (%s)" %
                        (self._host, self._port, e))
                return
            except socket.error, e:
                self._log.error("Unable to connect to %s:%d (%s). "
                        "Attempts left: %d" %
                        (self._host, self._port, e, self._retry))
                if self._retry < 1:
                    return
            except:
                self._log.error("Unable to connect to %s:%d (%s)")
                return
            else:
                break
            finally:
                s.close()

        while not self._terminate and self._paths:
            self._channels.clear()
            self._clients[:]
            self._clients = [self.create_client(self._host, self._paths,
                self._port, self._channels, self._loglevel)
                for i in xrange(0, min(self._async, len(self._paths)))]

            # start asynchronous requests
            asyncore.loop(map=self._channels)

            # find abortet request paths
            for client in self._clients:
                if client.unfinished_path():
                    self._paths.append(client.unfinished_path())

    def terminate(self):
        """Terminate the crawler and his clients."""
        self._log.debug("Terminate crawler %s" % self)
        self._terminate = True
        for client in self._clients:
            client.close()
