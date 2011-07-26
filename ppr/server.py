'''
File: server.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Functions to control services and execute commands.

Usage: python server.py [OPTIONS]

Options:
    -m, --mysqld    : mysqld service name
    -a, --archive   : wiki.tar path
    -d, --db        : mysql.tar path
    -w, --wiki      : wikipedia directory
    -q, --mysql     : mysql directory
    -h, --help      : print this message
'''
import sys
import subprocess
import shlex
import re


def execute(cmd, pipe=True):
    """
    Executes a command by subprocess module. Optional process output.

    cmd     : command to execute
    pipe    : trigger return of process output
    """
    args = shlex.split(cmd)
    if pipe:
        proc = subprocess.Popen(args, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE)
        output = proc.communicate()
        return proc.returncode, output
    else:
        proc = subprocess.Popen(args)
        proc.wait()
        return proc.returncode


def stop_service(log, service):
    """Stop a given service on the local system."""
    log.info("Check status of %s service", service)
    cmd = "service %s status" % service
    result, output = execute(cmd)
    if result == 1:
        log.error("Unknown service %s", service)
        sys.exit(2)
    if re.compile(r'|'.join(["start", "process", "PID"])).search(output[0]):
        log.info("Stop %s service", service)
        cmd = "service %s stop" % service
        result, output = execute(cmd)
        if result != 0:
            log.error("Unable to stop %s service", service)
            sys.exit(2)
        log.info("Service %s stopped", service)
    else:
        log.info("Service %s already stopped", service)


def start_service(log, service):
    """Start a given service on the local system."""
    cmd = "service %s status" % service
    result, output = execute(cmd)
    if re.compile(r'|'.join(["start", "process", "PID"])).search(output[0]):
        log.info("Service %s already started", service)
        return

    log.info("Start %s service", service)
    cmd = "service %s start" % service
    result, output = execute(cmd)
    if result != 0:
        log.error("Unable to start service %s", service)
        sys.exit(2)
    log.info("Service %s successful started", service)


def scp_files(host, user, files, exe, log, directory="~/"):
    """
    Copy a list of files to a given host address (by scp) and execute
    all given commands (by ssh).

    host        : hostname
    user        : username on host
    files       : list of files to copy
    exe         : list of commands to execute
    log         : logger instance
    directory   : directory to copy data on host system
    """

    params = dict()
    params["files"] = " ".join(files)
    params["user"] = user
    params["host"] = host
    params["dir"] = directory
    cmd = "scp %(files)s %(user)s@%(host)s:%(dir)s" % params
    log.info("Copy files to %s", host)
    log.debug("cmd: %s", cmd)
    result = execute(cmd, pipe=False)
    if result != 0:
        log.error("Unable to copy files")
    else:
        log.info("Successful copied files to %s", host)
        for cmd in exe:
            log.info("Execute '%s' on %s", cmd, host)
            params = dict()
            params["user"] = user
            params["host"] = host
            params["cmd"] = cmd
            cmd = "ssh %(user)s@%(host)s %(cmd)s" % params
            log.debug("cmd: %s", cmd)
            result = execute(cmd, pipe=False)
            if result != 0:
                log.error("Unable to execute '%s'", cmd)
            else:
                log.info("Successful executed command on %s", host)


def main():
    """Unpacks given mediawiki and mysql packages."""
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hm:a:d:w:q:",
                ["httpd=", "mysqld=", "archive=", "db=", "wiki=", "mysql=",
                "help"])

        for opt, value in opts:
            if opt in ["-h", "--help"]:
                print __doc__
                sys.exit(0)
            if opt in ["-m", "--mysqld"]:
                mysqld = value
            if opt in ["-a", "--archive"]:
                archive = value
            if opt in ["-d", "--database"]:
                database = value
            if opt in ["-w", "--wiki"]:
                wiki = value
            if opt in ["-q", "--mysql"]:
                mysql = value

        log = logging.getLogger()
        formatter = logging.Formatter(
            "%(asctime)s  %(levelname)s: %(message)s", "%d.%m.%Y %H:%M:%S")
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        log.addHandler(handler)
        log.setLevel(logging.DEBUG)

        if wiki != "None":

            if os.path.isdir(wiki):
                log.info("Remove wiki directory '%s'", wiki)
                shutil.rmtree(wiki)

            log.info("Unpack mediawiki '%s' to '%s'", archive, wiki)
            tar = tarfile.open(archive)
            tar.extractall(path=wiki)
            tar.close()

            images_dir = os.path.join(wiki, "images")

            log.info("Chmod 777 images dir '%s'", images_dir)
            result = execute("chmod -R 777 %s" % images_dir, pipe=False)
            if result == 0:
                log.info("Successful installed mediawiki")
            else:
                log.error("Unable to chmod 777 %s", images_dir)

        if mysql != "None":
            stop_service(log, mysqld)

            log.info("Unpack mysql database '%s' to '%s'", database, mysql)
            tar = tarfile.open(database)
            tar.extractall(path=mysql)
            tar.close()

            start_service(log, mysqld)

        sys.exit(0)

    except getopt.GetoptError, err:
        print >> sys.stderr, err
        print __doc__
        sys.exit(1)


if __name__ == '__main__':
    import getopt
    import logging
    import os.path
    import shutil
    import tarfile
    main()
