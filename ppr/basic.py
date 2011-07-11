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
                    except Queue.Empty, e:
                        pass
            finally:
                output.close()
        except IOError, e:
            self._log.error(e)
