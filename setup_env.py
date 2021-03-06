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
import ConfigParser
import gzip
import logging
import multiprocessing
import tarfile
from ppr.basic import Process, FileReader, SyncClient
from ppr.trace import WikiAnalyser, WikiFilter, FileCollector
from ppr.server import execute, stop_service, start_service


def print_error(msg, hint=""):
    """Print error message and exit."""
    print >> sys.stderr, "ERROR:", msg
    if hint:
        print >> sys.stderr, hint
    sys.exit(1)


def get_config(config, config_func, section, option, hint="", default=None):
    """Return a value from configuration file."""
    if config.has_option(section, option):
        return config_func(section, option)
    else:
        if default is None:
            print_error("Unable to find '%s' option in '%s' section" %
                    (option, section), "Hint: " + hint)
        else:
            return default


def get_config_str(config, section, option, hint="", default=None):
    """Return a string from configuration file."""
    return get_config(config, config.get, section, option, hint,
            default)


def get_config_bool(config, section, option, hint="", default=None):
    """Return a boolean from configuration file."""
    return get_config(config, config.getboolean, section, option, hint,
            default)


def get_config_int(config, section, option, hint="", default=None):
    """Return a integer from configuration file."""
    return get_config(config, config.getint, section, option, hint,
            default)


def get_config_path(config, section, option, hint="", default=None):
    """Return a path from configuration file."""
    return os.path.realpath(get_config(config, config.get, section, option,
        hint, default))


def split_server(server):
    """Split server configuration string."""
    if not server:
        return dict()
    try:
        result = dict()
        for cfg in server.split(":"):
            (config, ips) = cfg.split("@")
            result[config] = ips.split(",")
        return result
    except:
        print_error("Unable to parse 'server' option in 'download' section")


def read_config(filename):
    """Read configuration file."""
    config = dict()
    config_file = ConfigParser.SafeConfigParser()
    config_file.read([filename])

    # general
    config["analyse"] = get_config_bool(config_file, "general", "analyse",
            "Analyse trace file and write statistics")
    config["filter"] = get_config_bool(config_file, "general", "filter",
            "Filter trace file and analyse filtered trace file")
    config["download"] = get_config_bool(config_file, "general", "download",
            "Download images and thumbs from filtered trace file")
    config["install"] = get_config_bool(config_file, "general", "install",
            "Pack images and database and install them on other server")

    config["logging"] = get_config_str(config_file, "general", "logging",
            default=logging.DEBUG).upper()
    config["plot"] = get_config_bool(config_file, "general", "plot",
            default=False)

    # trace
    config["trace_file"] = get_config_path(config_file, "trace", "file",
            "Path of trace file")

    config["trace_gzip"] = get_config_bool(config_file, "trace", "gzip",
            default=False)
    if config["trace_gzip"]:
        config["trace_openfunc"] = gzip.open
    else:
        config["trace_openfunc"] = open

    if config["filter"] or config["download"]:
        # filter
        start, end = get_config_str(config_file, "filter", "interval",
                "Time interval to filter trace (timestamp:timestamp or "
                "timestamp:seconds)").split(":")
        start = float(start)
        end = float(end)
        if start >= end:
            end += start
        config["filter_interval"] = (start, end)

        config["filter_host"] = get_config_str(config_file, "filter", "host",
                "Host address for rewrite trace (name or IP)")

        config["filter_regex"] = get_config_str(config_file, "filter", "regex",
                default=WikiFilter.DEFAULT_REGEX)

        config["filter_gzip"] = get_config_bool(config_file, "filter", "gzip",
                False)
        if config["filter_gzip"]:
            config["filter_openfunc"] = gzip.open
        else:
            config["filter_openfunc"] = open

    if config["download"] or config["install"]:
        # download
        config["download_dir"] = get_config_path(config_file, "download",
                "download_dir", "Directory to download images and thumbs from "
                "filter trace, also test if they already exist")

        config["download_port"] = get_config_int(config_file, "download",
                "port", default=80)

        config["download_async"] = get_config_int(config_file, "download",
                "async", default=25)

        config["download_wiki_dir"] = get_config_path(config_file, "download",
                "wiki_dir", "Mediawiki root directory")

        config["download_wiki_images"] = os.path.join(
                config["download_wiki_dir"], "images")

        config["download_clean_images"] = get_config_bool(config_file,
                "download", "clean_images", default=True)

        config["download_mysqld"] = get_config_str(config_file, "download",
                "mysqld", "MySQL service name on localhost, used to stop and "
                "start the database during packing the content")

        config["download_mysql_dir"] = get_config_path(config_file, "download",
                "mysql_dir", "MySQL directory, packed for installation on "
                "other server")

        config["download_clean_mysql"] = get_config_bool(config_file,
                "download", "clean_mysql", default=True)

        config["download_mysql_archive"] = get_config_path(config_file,
                "download", "mysql_archive", default="")

        config["download_output_dir"] = get_config_path(config_file,
                "download", "output_dir", "Directory to save packed images "
                "and database for exchange")

    if config["install"]:
        config["install_server"] = split_server(get_config_str(config_file,
                "install", "server", default=""))

        config["install_server_config"] = dict()
        for sconfig in config["install_server"]:
            # server config
            cfg = dict()
            cfg["user"] = get_config_str(config_file, sconfig, "user",
                    "Username on server")
            cfg["copy_dir"] = get_config_str(config_file, sconfig, "copy_dir",
                    default="~/")
            cfg["wiki_dir"] = get_config_str(config_file, sconfig, "wiki_dir",
                    default="None")
            cfg["mysqld"] = get_config_str(config_file, sconfig, "mysqld",
                    default="mysqld")
            cfg["mysql_dir"] = get_config_str(config_file, sconfig,
                    "mysql_dir", default="None")
            config["install_server_config"][sconfig] = cfg

    return config


def pack_db(log, script, output_dir, mysql_dir, mysql_pack, service):
    """Pack MySQL database to tar file."""
    cmd = " ".join(["php", script, "--missing"])
    result, output = execute(cmd)
    if output[0]:
        log.debug("\n%s", output[0])
    if output[1]:
        log.error("\n%s", output[1])

    if not os.path.isdir(output_dir):
        log.info("Create output directory %s", output_dir)
        os.makedirs(output_dir)

    log.info("Pack mysql db to %s", mysql_pack)
    stop_service(log, service)
    tar = tarfile.open(mysql_pack, "w")
    for filename in os.listdir(mysql_dir):
        tar.add(os.path.join(mysql_dir, filename), arcname=filename)
    tar.close()
    start_service(log, service)


def pack_mediawiki(wiki_pack, wiki_dir):
    """Pack mediawiki to tar file."""
    tar = tarfile.open(wiki_pack, "w")
    for filename in os.listdir(wiki_dir):
        tar.add(os.path.join(wiki_dir, filename), arcname=filename)
    tar.close()


def main(config):
    """Setup wikipedia enviroment and sync it."""

    log = multiprocessing.get_logger()

    Process.DEFAULT_LOGLEVEL = logging.getLevelName(config["logging"])

    # test required values
    if config["analyse"] or config["filter"] or config["download"]:
        trace_file = config["trace_file"]
        if not os.path.isfile(trace_file):
            print_error("Unable to find tracefile " + trace_file)

    if config["download"] or config["install"]:
        output_dir = config["download_output_dir"]
        mysql_pack = os.path.join(output_dir, "mysql.tar")
        wiki_pack = os.path.join(output_dir, "wiki.tar")
        if not config["download"]:
            if not os.path.isfile(mysql_pack):
                print_error("Unable to find packed database " + mysql_pack)
            if not os.path.isfile(wiki_pack):
                print_error("Unable to find packed mediawiki " + wiki_pack)

    if config["download"]:
        filterfile = WikiFilter.get_filterfile(trace_file,
                config["filter_interval"])
        imagefile = WikiAnalyser.get_special_file(filterfile, "image")
        thumbfile = WikiAnalyser.get_special_file(filterfile, "thumb")
        wiki_images = config["download_wiki_images"]

        if not config["filter"] and not os.path.isfile(imagefile):
            print_error("Unable to find filtered image trace " + imagefile)

        if not config["filter"] and not os.path.isfile(thumbfile):
            print_error("Unable to find filtered thumb trace " + thumbfile)

        if not os.path.isdir(wiki_images):
            print_error("Unable to find wiki images dir " + wiki_images)

        mysql_dir = config["download_mysql_dir"]
        if not os.path.isdir(mysql_dir):
            print_error("Unable to find mysql dir " +
                    config["download_mysql_dir"])

        script = os.path.join(config["download_wiki_dir"],
                "maintenance/rebuildImages.php")
        if not os.path.isfile(script):
            print_error("Unable to find wiki script " + script)

        if config["download_clean_mysql"]:
            archive = config["download_mysql_archive"]

            if not os.path.isfile(archive):
                print_error("Unable to find mysql clean archive " +
                        config["download_mysql_archive"])

    # analyse and filter
    reader_pipes = []
    if config["analyse"]:
        analyser = WikiAnalyser(trace_file, config["trace_openfunc"],
                config["plot"])
        analyser.start()
        reader_pipes.append(analyser.pipe)

    if config["filter"]:
        wfilter = WikiFilter(trace_file, config["filter_host"],
                config["filter_interval"], config["filter_regex"],
                True, config["filter_openfunc"], config["plot"])
        wfilter.start()
        reader_pipes.append(wfilter.pipe)

    if reader_pipes:
        reader = FileReader(trace_file, config["trace_openfunc"],
                reader_pipes)
        reader.start()
        reader.join()

    if config["analyse"]:
        analyser.join()
    if config["filter"]:
        wfilter.join()

    # download
    if config["download"]:
        if config["download_clean_images"]:
            log.debug("Remove wiki image directory %s", wiki_images)
            shutil.rmtree(wiki_images)
            log.debug("Create wiki image directory %s", wiki_images)
            os.makedirs(wiki_images)

        image_collector = FileCollector(config["download_dir"], wiki_images,
                config["filter_regex"], config["download_port"],
                config["download_async"])
        image_reader = FileReader(imagefile, config["filter_openfunc"],
                pipes=[image_collector.pipe])
        image_reader.start()
        image_collector.start()

        thumb_collector = FileCollector(config["download_dir"], wiki_images,
                config["filter_regex"], config["download_port"],
                config["download_async"])
        thumb_reader = FileReader(thumbfile, config["filter_openfunc"],
                pipes=[thumb_collector.pipe])
        thumb_reader.start()
        thumb_collector.start()

        image_reader.join()
        thumb_reader.join()
        image_collector.join()
        thumb_collector.join()

        log.info("Chmod 777 images dir '%s'", wiki_images)
        result = execute("chmod -R 777 %s" % wiki_images, pipe=False)
        if result == 0:
            log.info("Successful setup mediawiki")
        else:
            log.error("Unable to chmod 777 %s", wiki_images)

        service = config["download_mysqld"]

        if config["download_clean_mysql"]:
            stop_service(log, service)

            log.info("Unpack clean mysql db %s to %s", archive, mysql_dir)
            tar = tarfile.open(archive)
            tar.extractall(path=mysql_dir)
            tar.close()
            log.info("Clean mysql db successful unpacked")

        start_service(log, service)

        log.info("Import images to database")
        p_db = multiprocessing.Process(target=pack_db, args=(log, script,
            output_dir, mysql_dir, mysql_pack, service))
        p_db.start()

        log.info("Pack mediawiki to %s", wiki_pack)
        p_images = multiprocessing.Process(target=pack_mediawiki, args=(
            wiki_pack, config["download_wiki_dir"]))
        p_images.start()
        p_images.join()
        p_db.join()

    # install
    if config["install"]:
        server = config["install_server"]
        sconfig = config["install_server_config"]

        script = os.path.realpath("ppr/server.py")
        sync = []

        for cfg in server:
            for host in server[cfg]:
                sclient = SyncClient(host, sconfig[cfg], wiki_pack, mysql_pack,
                        script)
                sclient.start()
                sync.append(sclient)

        for sclient in sync:
            sclient.join()


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print_error("Need one config file", __doc__)

    if not os.path.isfile(sys.argv[1]):
        print_error("Unable to find config file", __doc__)

    main(read_config(sys.argv[1]))
    sys.exit(0)
