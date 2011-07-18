'''
File: server.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Functions to control services and execute commands.

Usage: python server.py [OPTIONS]

Options:
    -m, --mysqld    : mysqld service name
    -i, --images    : image.tar path
    -d, --db        : mysql archive path
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
    log.info("Check status of %s service" % service)
    cmd = "service %s status" % service
    rc, output = execute(cmd)
    if rc == 1:
        log.error("Unknown service " + service)
        sys.exit(2)
    if re.compile(r'|'.join(["start", "process", "PID"])).search(output[0]):
        log.info("Stop %s service" % service)
        cmd = "service %s stop" % service
        rc, output = execute(cmd)
        if rc != 0:
            log.error("Unable to stop %s service" % service)
            sys.exit(2)
        log.info("Service %s stopped" % service)
    else:
        log.info("Service %s already stopped" % service)


def start_service(log, service):
    cmd = "service %s status" % service
    rc, output = execute(cmd)
    if re.compile(r'|'.join(["start", "process", "PID"])).search(output[0]):
        log.info("Service %s already started", service)
        return

    log.info("Start %s service" % service)
    cmd = "service %s start" % service
    rc, output = execute(cmd)
    if rc != 0:
        log.error("Unable to start service " + service)
        sys.exit(2)
    log.info("Service %s successful started" % service)


def scp_files(host, user, files, exe, log, directory="~/"):
    vars = dict()
    vars["files"] = " ".join(files)
    vars["user"] = user
    vars["host"] = host
    vars["dir"] = directory
    cmd = "scp %(files)s %(user)s@%(host)s:%(dir)s" % vars
    print cmd
    log.info("Copy files to %s", host)
    log.debug("cmd: %s", cmd)
    rc = execute(cmd, pipe=False)
    if rc != 0:
        log.error("Unable to copy files")
    else:
        log.info("Successful copied files to %s", host)
        for cmd in exe:
            log.info("Execute '%s' on %s", cmd, host)
            vars = dict()
            vars["user"] = user
            vars["host"] = host
            vars["cmd"] = cmd
            cmd = "ssh %(user)s@%(host)s %(cmd)s" % vars
            log.debug("cmd: %s", cmd)
            rc = execute(cmd, pipe=False)
            if rc != 0:
                log.error("Unable to execute '%s'", cmd)
            else:
                log.info("Successful executed command on %s", host)


if __name__ == '__main__':
    import getopt
    import logging
    import os.path
    import shutil
    import tarfile

    try:
        opts, args = getopt.getopt(sys.argv[1:], "hm:i:d:w:q:",
                ["httpd=", "mysqld=", "images=", "db=", "wiki=", "mysql=",
                "help"])

        for o, a in opts:
            if o in ["-h, --help"]:
                print __doc__
                sys.exit(0)
            if o in ["-m", "--mysqld"]:
                mysqld = a
            if o in ["-i", "--images"]:
                images= a
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
            images_dir = os.path.realpath(os.path.join(wiki, "images"))

            log.info("Remove images directory '%s'", images_dir)
            shutil.rmtree(images_dir)

            log.info("Unpack images '%s' to '%s'", images, images_dir)
            tar = tarfile.open(images)
            tar.extractall(path=images_dir)
            tar.close()

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
