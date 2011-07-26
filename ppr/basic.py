'''
File: basic.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Basic classes for project.
'''

import sys
import logging
import multiprocessing
import os.path
from server import scp_files


class Process(multiprocessing.Process):
    """Basic process class."""

    DEFAULT_LOGLEVEL = logging.DEBUG

    def __init__(self, output=sys.stdout, loglevel=None):
        """
        Create a new process.

        output      : output to write log messages
        loglevel    : log level

        """
        multiprocessing.Process.__init__(self)
        if loglevel is None:
            loglevel = Process.DEFAULT_LOGLEVEL
        self._log = multiprocessing.get_logger()
        if not self._log.handlers:
            self.create_log_handler(output, loglevel)
        self._log.debug("Process created %s", self.name)

    def create_log_handler(self, output, loglevel):
        """Create a new handler for logger."""
        formatter = logging.Formatter(
            "%(asctime)s %(processName)s %(threadName)s %(levelname)8s: "
            "%(message)s", "%d.%m.%Y %H:%M:%S")
        handler = logging.StreamHandler(output)
        handler.setFormatter(formatter)
        self._log.addHandler(handler)
        self.set_log_level(loglevel)
        self._log.debug("New handler added to logger")

    def set_log_level(self, loglevel):
        """Set log level."""
        if self._log.level != loglevel:
            self._log.setLevel(loglevel)
            self._log.debug("Set log level to: %d", loglevel)


class FileReader(Process):
    """Basic file reader process."""

    def __init__(self, filename, openfunc=open, pipes=[]):
        """
        Create a new reader.

        filename    : file to read
        openfunc    : function to open file
        pipes       : list of pipes to send lines

        """
        Process.__init__(self)
        self._filename = filename
        self._openfunc = openfunc
        self._pipes = pipes
        self._log.debug("FileReader for %s created with %d pipes", filename,
                len(pipes))

    def read(self, line):
        """Read line and send to all pipes."""
        for pipe in self._pipes:
            pipe.send(line)

    def run(self):
        """Process run method."""
        self._log.info("FileReader for %s started", self._filename)

        if self._pipes:
            finput = self._openfunc(self._filename, "r")
            try:
                for line in finput:
                    self.read(line.strip())
            finally:
                finput.close()
                self._log.debug("Send done message to all pipes")
                for pipe in self._pipes:
                    pipe.send(None)
                    pipe.close()
        else:
            self._log.warning("No pipes given")
        self._log.info("FileReader for %s finished", self._filename)


class PipeReader(Process):
    """Process that consumes data from a pipe."""

    DEFAULT_TIMEOUT = 1800

    def __init__(self, timeout=None):
        """
        Create new reader.

        timeout     : pipe poll timeout

        """
        Process.__init__(self)
        if timeout is None:
            timeout = PipeReader.DEFAULT_TIMEOUT
        (self._pipe, self.pipe) = multiprocessing.Pipe(duplex=False)
        self._timeout = timeout

    def consume(self, data):
        """Consume received data."""
        pass

    def run(self):
        """Process run method."""
        while True:
            if self._pipe.poll(self._timeout):
                data = self._pipe.recv()
                if data is None:
                    self._log.debug("Received done message")
                    break
                else:
                    self.consume(data)
            else:
                self._log.error("Timeout expired (Closing pipe)")
                break
        self._pipe.close()


class FileWriter(PipeReader):
    """Basic file writer process."""

    def __init__(self, filename, openfunc=open, timeout=None):
        """
        Create a new writer.

        filename    : file to write
        openfunc    : function to open file
        timout      : pipe poll timeout

        """
        PipeReader.__init__(self, timeout)
        self._filename = filename
        self._openfunc = openfunc
        self._output = None
        self._log.debug("FileWriter for %s created", filename)

    def consume(self, line):
        """Write received line to file."""
        self._output.write(line + "\n")

    def run(self):
        """Process run method."""
        self._log.info("FileWriter for %s started", self._filename)
        self._output = self._openfunc(self._filename, "w")
        self._log.debug("Write file %s", self._filename)
        try:
            PipeReader.run(self)
        finally:
            self._output.close()
        self._log.info("FileWriter for %s finished", self._filename)


class SyncClient(Process):
    """Client to sync a remote server."""

    def __init__(self, host, config, wiki_file, mysql_file, script):
        """
        Create a new client.

        host        : host to sync
        config      : config for sync
        wiki_file   : wiki.tar archive
        mysql_file  : mysql.tar archive
        script      : script name to execute

        """
        Process.__init__(self)
        self._host = host
        self._config = config
        self._wiki_file = wiki_file
        self._mysql_file = mysql_file
        self._script = script

    def run(self):
        """Process run method."""
        user = self._config["user"]
        files = [self._wiki_file, self._mysql_file, self._script]
        params = dict()
        params["dir"] = self._config["copy_dir"]
        params["script"] = os.path.split(self._script)[1]
        params["mysqld"] = self._config["mysqld"]
        params["archive"] = os.path.split(self._wiki_file)[1]
        params["db"] = os.path.split(self._mysql_file)[1]
        params["wiki"] = self._config["wiki_dir"]
        params["mysql"] = self._config["mysql_dir"]
        exe = ["python %(dir)s%(script)s -m %(mysqld)s -a %(dir)s%(archive)s "
                "-d %(dir)s%(db)s -w %(wiki)s -q %(mysql)s" % params]
        self._log.info("SCP files: %s", ", ".join(files))
        scp_files(self._host, user, files, exe, self._log,
                self._config["copy_dir"])
