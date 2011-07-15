'''
File: basic.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Basic classes for project.
'''

import sys
import logging
import multiprocessing


class Process(multiprocessing.Process):
    """ Basic process class. """

    def __init__(self, output=sys.stdout, loglevel=logging.WARNING):
        multiprocessing.Process.__init__(self)
        self._log = multiprocessing.get_logger()
        if not self._log.handlers:
            self.create_log_handler(output, loglevel)
        self._log.debug("Process created %s" % self.name)

    def create_log_handler(self, output, loglevel):
        formatter = logging.Formatter(
            "%(asctime)s %(processName)s %(threadName)s %(levelname)8s: "
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


class FileReader(Process):
    """ Basic file reader process. """

    def __init__(self, filename, openfunc=open, pipes=[]):
        Process.__init__(self)
        self._filename = filename
        self._openfunc = openfunc
        self._pipes = pipes
        self._log.debug("FileReader for %s created with %d pipes" %
                (filename, len(pipes)))

    def read(self, line):
        for pipe in self._pipes:
            pipe.send(line)

    def run(self):
        self._log.info("FileReader for %s started" % self._filename)

        if self._pipes:
            input = self._openfunc(self._filename, "r")
            try:
                for line in input:
                    self.read(line.strip())
            finally:
                input.close()
                self._log.debug("Send done message to all pipes (%s)" %
                        PipeReader.DONE)
                for pipe in self._pipes:
                    pipe.send(PipeReader.DONE)
                    pipe.close()
        else:
            self._log.warning("No pipes given")
        self._log.info("FileReader for %s finished" % self._filename)


class PipeReader(Process):
    """Process that consumes data from a pipe."""

    DONE = "###DONE###"
    DEFAULT_TIMEOUT = 1800

    def __init__(self, timeout=DEFAULT_TIMEOUT):
        Process.__init__(self)
        (self._pipe, self.pipe) = multiprocessing.Pipe(duplex=False)
        self._timeout = timeout

    def consume(self, data):
        pass

    def run(self):
        while True:
            if self._pipe.poll(self._timeout):
                data = self._pipe.recv()
                if data == PipeReader.DONE:
                    self._log.debug("Received done message (%s)" % data)
                    break
                else:
                    self.consume(data)
            else:
                self._log.error("Timeout expired (Closing pipe)")
                break
        self._pipe.close()


class FileWriter(PipeReader):
    """ Basic file writer process. """

    def __init__(self, filename, openfunc=open,
            timeout=PipeReader.DEFAULT_TIMEOUT):
        PipeReader.__init__(self, timeout)
        self._filename = filename
        self._openfunc = openfunc
        self._log.debug("FileWriter for %s created" % filename)

    def consume(self, line):
        self._output.write(line + "\n")

    def run(self):
        self._log.info("FileWriter for %s started" % self._filename)
        self._output = self._openfunc(self._filename, "w")
        self._log.debug("Write file %s", self._filename)
        try:
            PipeReader.run(self)
        finally:
            self._output.close()
        self._log.info("FileWriter for %s finished" % self._filename)
