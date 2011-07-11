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
    """ Basic process class"""

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
