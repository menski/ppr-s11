#!/usr/bin/env python2.6
'''
File: setup_env.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Python script to setup the wikipedia enviroment.

Usage:
    python2.6 setup_env.py CONFIG_FILE
'''

import sys
import os
import shutil
import os.path
import ConfigParser
import gzip
import logging
import subprocess
import shlex
import multiprocessing
import tarfile
from ppr.basic import Process, FileReader
from ppr.trace import WikiAnalyser, WikiFilter, FileCollector


def print_error(msg, hint=""):
    print >> sys.stderr, "ERROR:", msg
    if hint:
        print >> sys.stderr, hint
    sys.exit(1)


def get_config(config, config_func, section, option, hint="", default=None):
    if config.has_option(section, option):
        return config_func(section, option)
    else:
        if default is None:
            print_error("Unable to find '%s' option in '%s' section" %
                    (option, section), "Hint: " + hint)
        else:
            return default


def get_config_path(config, section, option, hint="", default=None):
    return os.path.realpath(get_config(config, config.get, section, option,
        hint, default))


def read_config(config_filename):
    config = dict()
    config_file = ConfigParser.SafeConfigParser()
    config_file.read([config_filename])

    # general
    config["analyse"] = get_config(config_file, config_file.getboolean,
            "general", "analyse", "analyse traces?")
    config["filter"] = get_config(config_file, config_file.getboolean,
            "general", "filter", "filter traces?")
    config["download"] = get_config(config_file, config_file.getboolean,
            "general", "download", "download images?")
    config["install"] = get_config(config_file, config_file.getboolean,
            "general", "install", "install mediawiki on other maschines?")

    config["logging"] = get_config(config_file, config_file.get,
            "general", "logging", default=logging.DEBUG).upper()

    # trace
    config["trace_file"] = get_config_path(config_file, "trace", "file",
            "path to trace file")

    config["trace_gzip"] = get_config(config_file, config_file.getboolean,
            "trace", "gzip", default=False)
    if config["trace_gzip"]:
        config["trace_openfunc"] = gzip.open
    else:
        config["trace_openfunc"] = open

    if config["filter"] or config["download"]:
        # filter
        a, b = get_config(config_file, config_file.get,
                "filter", "interval", "time interval to filter trace "
                "(timestamp:timestamp or timestamp:seconds)").split(":")
        a = float(a)
        b = float(b)
        if a >= b:
            b += a
        config["filter_interval"] = (a, b)

        config["filter_host"] = get_config(config_file, config_file.get,
                "filter", "host", "host for rewrite urls")

        config["filter_regex"] = get_config(config_file, config_file.get,
                "filter", "regex", default=WikiFilter.DEFAULT_REGEX)

        config["filter_gzip"] = get_config(config_file, config_file.getboolean,
                "filter", "gzip", False)
        if config["filter_gzip"]:
            config["filter_openfunc"] = gzip.open
        else:
            config["filter_openfunc"] = open

    if config["download"]:
        # download
        config["download_dir"] = get_config(config_file, config_file.get,
                "download", "download_dir", "directory to download images")
        config["download_dir"] = os.path.abspath(config["download_dir"])

        config["download_port"] = get_config(config_file, config_file.getint,
                "download", "port", default=80)

        config["download_async"] = get_config(config_file, config_file.getint,
                "download", "async", default=25)

        config["download_wiki_dir"] = get_config_path(config_file, "download",
                "wiki_dir", "wiki directory to copy images to")

        config["download_wiki_images"] = os.path.join(
                config["download_wiki_dir"], "images")

        config["download_clean_images"] = get_config(config_file,
                config_file.getboolean, "download", "clean_images",
                default=True)

        config["download_mysqld"] = get_config(config_file, config_file.get,
                "download", "mysqld", "mysqld process name")

        config["download_mysql_dir"] = get_config_path(config_file, "download",
                "mysql_dir", "mysql directory")

        config["download_clean_mysql"] = get_config(config_file,
                config_file.getboolean, "download", "clean_mysql",
                default=True)

        config["download_mysql_archive"] = get_config_path(config_file,
                "download", "mysql_archive", default="")

    return config


def execute(cmd, pipe=True):
    args = shlex.split(cmd)
    if pipe:
        p = subprocess.Popen(args, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        output = p.communicate()
        return p.returncode, output
    else:
        p = subprocess.Popen(args)
        p.wait()
        return p.returncode


def stop_mysql(log, service):
    log.info("Check status of %s service" % service)
    cmd = "service %s status" % service
    rc, output = execute(cmd)
    if rc != 0:
        log.error("Unknown service " + service)
        sys.exit(2)
    if "start" in output[0]:
        log.info("Stop %s service" % service)
        cmd = "service %s stop" % service
        rc, output = execute(cmd)
        if rc != 0:
            log.error("Unable to stop %s service" % service)
            sys.exit(2)
        log.info("Service %s stopped" % service)
    else:
        log.info("Service %s already stopped" % service)


def start_mysql(log, service):
    log.info("Start %s service" % service)
    cmd = "service %s start" % service
    rc, output = execute(cmd)
    if rc != 0:
        log.error("Unable to start service " + service)
        sys.exit(2)
    else:
        cmd = "service %s status" % service
        rc, output = execute(cmd)
        if "start" in output[0]:
            log.info("Service %s successful started" % service)
        else:
            log.error("Unknown error during start of %s service" %
                    service)
            sys.exit(2)


def main(config):

    log = multiprocessing.get_logger()

    # analyse and filter
    Process.DEFAULT_LOGLEVEL = logging.getLevelName(config["logging"])

    if config["analyse"] or config["filter"]:
        if not os.path.isfile(config["trace_file"]):
            print_error("Unable to find tracefile " + config["trace_file"])

    reader_pipes = []
    if config["analyse"]:
        analyser = WikiAnalyser(config["trace_file"], config["trace_openfunc"])
        analyser.start()
        reader_pipes.append(analyser.pipe)

    if config["filter"]:
        filter = WikiFilter(config["trace_file"], config["filter_host"],
                config["filter_interval"], config["filter_regex"],
                True, config["filter_openfunc"])
        filter.start()
        reader_pipes.append(filter.pipe)

    if reader_pipes:
        reader = FileReader(config["trace_file"], config["trace_openfunc"],
                reader_pipes)
        reader.start()
        reader.join()

    if config["analyse"]:
        analyser.join()
    if config["filter"]:
        filter.join()

    # download and install

    if config["download"]:
        filterfile = WikiFilter.get_filterfile(config["trace_file"],
                config["filter_interval"])
        (path, ext) = os.path.splitext(filterfile)
        imagefile = WikiAnalyser.get_special_file(filterfile, "image")
        thumbfile = WikiAnalyser.get_special_file(filterfile, "thumb")

        if not os.path.isfile(imagefile):
            print_error("Unable to find filtered image trace " + imagefile)

        if not os.path.isfile(thumbfile):
            print_error("Unable to find filtered thumb trace " + thumbfile)

        if not os.path.isdir(config["download_wiki_images"]):
            print_error("Unable to find wiki images dir " +
                    config["download_wiki_images"])

        if config["download_clean_images"]:
            shutil.rmtree(config["download_wiki_images"])
            os.makedirs(config["download_wiki_images"])

        image_collector = FileCollector(config["download_dir"],
                config["download_wiki_images"], config["filter_regex"],
                config["download_port"], config["download_async"])
        thumb_collector = FileCollector(config["download_dir"],
                config["download_wiki_images"], config["filter_regex"],
                config["download_port"], config["download_async"])
        image_reader = FileReader(imagefile, config["filter_openfunc"],
                pipes=[image_collector.pipe])
        image_reader.start()
        image_collector.start()
        thumb_reader = FileReader(thumbfile, config["filter_openfunc"],
                pipes=[thumb_collector.pipe])
        thumb_reader.start()
        thumb_collector.start()

        image_reader.join()
        thumb_reader.join()
        image_collector.join()
        thumb_collector.join()

        if config["download_clean_mysql"]:
            if not os.path.isdir(config["download_mysql_dir"]):
                log.error("Unable to find mysql dir " +
                        config["download_mysql_dir"])
                sys.exit(2)

            if not os.path.isfile(config["download_mysql_archive"]):
                log.error("Unable to find mysql clean archive " +
                        config["download_mysql_archive"])
                sys.exit(2)

            service = config["download_mysqld"]

            stop_mysql(log, service)

            mysql_dir = config["download_mysql_dir"]
            archive = config["download_mysql_archive"]

            log.info("Unpack clean mysql db %s to %s" % (archive, mysql_dir))
            tar = tarfile.open(archive)
            tar.extractall(path=mysql_dir)
            tar.close()
            log.info("Clean mysql db successful unpacked")

            start_mysql(log, service)

            script = os.path.join(config["download_wiki_dir"],
                    "maintenance/rebuildImages.php")
            if not os.path.isfile(script):
                log.error("Unable to find wiki script " + script)
                sys.exit(2)

            log.info("Import images to database")
            cmd = " ".join(["php", script, "--missing"])
            rc, output = execute(cmd)
            if output[0]:
                log.debug("\n" + output[0])
            if output[1]:
                log.error("\n" + output[1])

            mysql_pack = "mysql.tar.bz"
            log.info("Pack mysql db to %s" % mysql_pack)
            stop_mysql(log, service)
            tar = tarfile.open(mysql_pack, "w:bz2")
            for f in os.listdir(mysql_dir):
                tar.add(os.path.join(mysql_dir, f), arcname=f)
            tar.close()
            start_mysql(log, service)

            image_pack = "image.tar"
            log.info("Pack images to %s" % image_pack)
            tar = tarfile.open(image_pack, "w")
            for f in os.listdir(config["download_wiki_images"]):
                tar.add(os.path.join(config["download_wiki_images"], f),
                        arcname=f)
            tar.close()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print_error("Need one config file", __doc__)

    config_filename = sys.argv[1]

    if not os.path.isfile(config_filename):
        print_error("Unable to find config file", __doc__)

    main(read_config(config_filename))
