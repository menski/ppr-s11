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


def stop_service(log, service):
    log.info("Check status of %s service", service)
    cmd = "service %s status" % service
    rc, output = execute(cmd)
    if rc == 1:
        log.error("Unknown service %s", service)
        sys.exit(2)
    if re.compile(r'|'.join(["start", "process", "PID"])).search(output[0]):
        log.info("Stop %s service", service)
        cmd = "service %s stop" % service
        rc, output = execute(cmd)
        if rc != 0:
            log.error("Unable to stop %s service", service)
            sys.exit(2)
        log.info("Service %s stopped", service)
    else:
        log.info("Service %s already stopped", service)


def start_service(log, service):
    cmd = "service %s status" % service
    rc, output = execute(cmd)
    if re.compile(r'|'.join(["start", "process", "PID"])).search(output[0]):
        log.info("Service %s already started", service)
        return

    log.info("Start %s service", service)
    cmd = "service %s start" % service
    rc, output = execute(cmd)
    if rc != 0:
        log.error("Unable to start service %s", service)
        sys.exit(2)
    log.info("Service %s successful started", service)


def scp_files(host, user, files, exe, log, directory="~/"):
    params = dict()
    params["files"] = " ".join(files)
    params["user"] = user
    params["host"] = host
    params["dir"] = directory
    cmd = "scp %(files)s %(user)s@%(host)s:%(dir)s" % params
    log.info("Copy files to %s", host)
    log.debug("cmd: %s", cmd)
    rc = execute(cmd, pipe=False)
    if rc != 0:
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
            rc = execute(cmd, pipe=False)
            if rc != 0:
                log.error("Unable to execute '%s'", cmd)
            else:
                log.info("Successful executed command on %s", host)


def main():
    try:
        opts, args = getopt.getopt(sys.argv[1:], "hm:a:d:w:q:",
                ["httpd=", "mysqld=", "archive=", "db=", "wiki=", "mysql=",
                "help"])

        for o, a in opts:
            if o in ["-h", "--help"]:
                print __doc__
                sys.exit(0)
            if o in ["-m", "--mysqld"]:
                mysqld = a
            if o in ["-a", "--archive"]:
                archive = a
            if o in ["-d", "--db"]:
                db = a
            if o in ["-w", "--wiki"]:
                wiki = a
            if o in ["-q", "--mysql"]:
                mysql = a

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

            log.info("Unpack mysql database '%s' to '%s'", db, mysql)
            tar = tarfile.open(db)
            tar.extractall(path=mysql)
            tar.close()

            start_service(log, mysqld)

        sys.exit(0)

    except getopt.GetoptError, e:
        print >> sys.stderr, e
        print __doc__
        sys.exit(1)


if __name__ == '__main__':
    import getopt
    import logging
    import os.path
    import shutil
    import tarfile
    main()
