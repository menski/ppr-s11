#!/usr/bin/env python
'''
File: fetcher.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: A MySQL fetcher for the wikipedia page table.

Usage: fetcher.py [OPTIONS]

Options:
    -h, --host      : MySQL host name (default: localhost)
    -u, --user      : MySQL username (default: wikipedia)
    -p, --passwd    : MySQL password (default: wikipedia)
    -d, --db        : MySQL database (default: wikipedia)
    -t, --table     : MySQL table (default: page)
    -c, --columns   : Comma separated list of column names to fetch
                      (default: "page_namespace,page_title")
    -f, --function  : Function to process fetched row
                      (see Functions, default: quoted)
    --help          : Print this help message

Functions:
    p, plain        : print unquoted wikipedia url
    q, quoted       : print quoted wikipedia url
    c, column       : print plain result without wikipedia url
'''

import sys
import getopt
import urllib
import MySQLdb as mysql

WIKI_PATH = "/wiki/index.php?namespace=%d&title=%s"


def fetchdb(host, user, passwd, db, table, columns, fun=None):
    """
    Fetch all entries from a MySQL database table and process them.

    Attributes:
    - `host` : MySQL host name
    - `user` : MySQL username
    - `passwd` : MySQL password
    - `db` : MySQL database
    - `table` : MySQL table
    - `columns` : table columns to fetch
    - `fun` : function to process results

    """

    try:
        conn = mysql.connect(host, user, passwd, db)
        cursor = conn.cursor()
        select = "SELECT %s FROM %s" % (", ".join(columns), table)
        cursor.execute(select)
        for row in cursor.fetchall():
            if fun is not None:
                fun(row)
            else:
                print " ".join([str(i) for i in row])
        cursor.close()
        conn.close()
    except mysql.Error, e:
        print e


def quoted(row):
    """Print the fetched, quoted row as wikipedia url."""
    print WIKI_PATH % (row[0], urllib.quote(row[1]))


def plain(row):
    """Print the fetched, unquoted row as wikipedia url."""
    print WIKI_PATH % (row[0], row[1])


def column(row):
    """Print the fetch row without wikipedia url"""
    print " ".join([str(i) for i in row])


def main():
    """Start fetcher with sys.args."""
    try:
        opts, args = getopt.getopt(sys.argv[1:], "h:u:p:d:t:c:f:",
                ["host=", "user=", "passwd=", "db=", "table=", "columns=",
                "function=", "help"])
    except getopt.GetoptError, e:
        print >> sys.stderr, e
        print __doc__
        sys.exit(2)

    # defaults
    host = "localhost"
    user = "wikipedia"
    passwd = "wikipedia"
    db = "wikipedia"
    table = "page"
    columns = ["page_namespace", "page_title"]
    fun = quoted

    # process options
    for o, a in opts:
        if o == "--help":
            print __doc__
            sys.exit(0)
        elif o in ("-h", "--host"):
            host = a
        elif o in ("-u", "--user"):
            user = a
        elif o in ("-p", "--passwd"):
            passwd = a
        elif o in ("-d", "--db"):
            db = a
        elif o in ("-t", "--table"):
            table = a
        elif o in ("-c", "--columns"):
            columns = a.split(",")
        elif o in ("-f", "--function"):
            if a in ("q", "quoted"):
                fun = quoted
            elif a in ("p", "plain"):
                fun = plain
            elif a in ("c", "column"):
                fun = column
            else:
                print >> sys.stderr, "Unknown function"
                sys.exit(2)

    fetchdb(host, user, passwd, db, table, columns, fun)


if __name__ == '__main__':
    main()
