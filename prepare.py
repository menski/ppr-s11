#!/usr/bin/env python
'''
File: prepare.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Prepare system for servload test.

Usage: prepare.py [OPTIONS]

Options:
    -f, --config    : Config file
    -h, --help      : Print this help message

'''

import getopt
import os.path
import sys
from ConfigParser import SafeConfigParser
import gzip
import re
from collections import deque
import logging
from httpasync import trace


log = logging.getLogger()
if not log.handlers:
    handler = logging.StreamHandler(sys.stdout)
    frm = logging.Formatter("%(asctime)s %(levelname)s: %(threadName)s "
        "%(message)s", "%d.%m.%Y %H:%M:%S")
    handler.setFormatter(frm)
    log.addHandler(handler)
    log.setLevel(logging.DEBUG)

def main():
    """Read config and prepare system for servload test."""
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hf:", ["help", "config="])
    except getopt.GetoptError, e:
        print >> sys.stderr, e
        print __doc__
        sys.exit(2)

    config = "ib.cfg"

    for o, a in opts:
        if o in ["-h", "--help"]:
            print __doc__
            sys.exit(0)
        if o in ["-f", "--config"]:
            config = a

    if not os.path.isfile(config):
        print >>sys.stderr, "ERROR: Unable to find config file '%s'\n" % (
                args.config)
        print __doc__
        sys.exit(1)

    cfgparser = SafeConfigParser()
    cfgparser.read(config)
    imgdir = os.path.abspath(cfgparser.get("general", "image_dir"))
    if not os.path.isdir(imgdir):
        print >>sys.stderr, "ERROR: Unable to find image directory '%s'\n" % (
                imgdir)
        print __doc__
        sys.exit(1)

    imgurls = os.path.abspath(cfgparser.get("general", "image_urls"))
    if not os.path.isfile(imgurls):
        print >>sys.stderr, "ERROR: Unable to find file '%s'\n" % (
                imgurls)
        print __doc__
        sys.exit(1)

    thumburls = os.path.abspath(cfgparser.get("general", "thumb_urls"))
    if not os.path.isfile(thumburls):
        print >>sys.stderr, "ERROR: Unable to find file '%s'\n" % (
                thumburls)
        print __doc__
        sys.exit(1)

    gz = cfgparser.get("general", "gzip")
    if gz:
        openfunc=gzip.open
    else:
        openfunc=open

    img_paths = read_path_file(imgurls, imgdir, openfunc)
    thumb_paths = read_path_file(thumburls, imgdir, openfunc)

    for host in img_paths:
        paths = deque(img_paths[host])
        size = len(paths)
        crawler = trace.ImageCrawler(host, paths, imgdir)
        crawler.start()
        crawler.join()
        not_found = crawler.not_found()
        stat = "Statistic: Unable to find %d/%d" % (len(not_found), size)
        for url in not_found:
            stat += "\n" + url
        log.debug(stat)

    for host in thumb_paths:
        paths = deque(thumb_paths[host])
        size = len(paths)
        crawler = trace.ImageCrawler(host, paths, imgdir)
        crawler.start()
        crawler.join()
        not_found = crawler.not_found()
        stat = "Statistic: Unable to find %d/%d" % (len(not_found), size)
        for url in not_found:
            stat += "\n" + url
        log.debug(stat)

def read_path_file(filename, imgdir, openfunc=open):
    HOST = r'http://(?P<host>([\w-]+\.)*\w+)(?P<prefix>/[\w-]+/[\w-]+)/'
    pattern = re.compile(HOST)
    hosts = dict()

    input = openfunc(filename)
    try:
        for line in input:
            line = line.strip()
            m = pattern.search(line)
            if m is not None:
                host = m.group('host')
                prefix = m.group('prefix')
                path = re.sub(HOST, '/', line)
                if os.path.isfile(os.path.join(imgdir, path[1:])):
                    log.debug("File already exists '%s'", path)
                else:
                    if host not in hosts:
                        hosts[host] = set()
                    hosts[host].add(prefix + path)
            else:
                log.error("Unable to parse line '%'" % line)
    finally:
        input.close()

    return hosts



if __name__ == '__main__':
    main()
