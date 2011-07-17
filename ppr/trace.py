'''
File: trace.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Basic classes for trace handling.
'''

from basic import PipeReader, FileWriter
from http import FileCrawler
import sys
import subprocess
import re
import time
import os.path
from operator import itemgetter
import urlparse
import urllib
import shutil


def gnuplot(title, data, filename, ylabel=None, xlabel=None, using=None,
        styles=["points"]):
    """Use gnuplot to plot given data. Optional save plot in a file."""
    with open("%s.log" % filename, "w") as output:
        # create process
        gnuplot = subprocess.Popen(["gnuplot", "-"], stdout=output,
                stderr=output, stdin=subprocess.PIPE)
        stdin = gnuplot.stdin

        # set title
        stdin.write('set title "%s"\n' % title)

        # set output
        stdin.write('set terminal postscript color enhanced\n')
        stdin.write('set output "%s.eps"\n' % filename)

        # set axis labels
        if xlabel is not None:
            stdin.write('set xlabel "%s"\n' % xlabel)
        if ylabel is not None:
            stdin.write('set ylabel "%s"\n' % ylabel)

        # set xtics
        #stdin.write('set xtics 5\n')

        # set grid
        stdin.write('set grid y\n')

        # set multiplot
        stdin.write('set multiplot\n')

        # create plot command
        plotcmd = 'plot "-"'
        if using is not None:
            plotcmd = " ".join([plotcmd, "using", using])
        plotcmd = " ".join([plotcmd, "notitle"])
        for style in styles:
            stdin.write(" ".join([plotcmd, "with", style]) + "\n")
            # data input
            for line in data:
                stdin.write(line + "\n")
            stdin.write("e\n")

        # unset multiplot
        stdin.write("unset multiplot\n")

        # quit process
        stdin.write("quit\n")
        return gnuplot.wait()


class TraceAnalyser(PipeReader):
    """Analyse a trace and output some statitics."""

    def __init__(self, filename, timeout=None):
        PipeReader.__init__(self, timeout)
        self._filename = filename
        self._gnuplot = gnuplot
        self.init()
        self._log.debug("TraceAnalyser for %s created" % filename)

    def init(self):
        """Initialize the analyzier."""
        pass

    def consume(self, line):
        """Analyse a trace line."""
        pass

    def stats(self):
        """Write statistics."""
        pass

    def plot(self):
        """Plot statistics."""
        pass

    def run(self):
        """Run analyse process."""
        self._log.info("TraceAnalyser for %s started" % self._filename)
        PipeReader.run(self)
        self.stats()
        self.plot()
        self._log.info("TraceAnalyser for %s finished" % self._filename)


class WikiAnalyser(TraceAnalyser):
    """Analyse a wiki trace from wikibench.eu"""

    def __init__(self, filename, openfunc=open, timeout=None):
        TraceAnalyser.__init__(self, filename, timeout)
        self._openfunc = openfunc

    def init(self):
        """Initialize the analyser."""
        self._lines = 0
        self._requests = 0
        self._errors = []
        self._starttime = time.time()
        self._endtime = 0
        self._hosts = dict()
        self._uploads = dict()
        self._images_set = set()
        self._images_host = dict()
        self._thumbs_set = set()
        self._thumbs_host = dict()
        self._methods = dict()
        self._rps = dict()

    def inc_dict(self, dictonary, key):
        """Create or increment a value in an dictonary"""
        if key in dictonary:
            dictonary[key] += 1
        else:
            dictonary[key] = 1

    def print_dict(self, dictonary, output):
        sformat = "%30s: %8d\n"
        sum = 0
        count = 0
        for key, value in sorted(dictonary.items(), key=itemgetter(1),
            reverse=True):
            sum += value
            count += 1
            output.write(sformat % (key, value))
        output.write("%40s\n" % "----------")
        output.write(sformat % ("sum", sum))
        output.write(sformat % ("count", count))

    def consume(self, line):
        """Analyse a trace line."""
        self._lines += 1

        # split line
        try:
            (nr, timestamp, url, method) = line.split(" ")
            split = urlparse.urlsplit(url)
            host = split.hostname
            path = split.path
        except Exception, e:
            self._log.critical("ERROR: Unable to parse line %s (%s)" %
                    (line, e))
            sys.exit(3)
        timestamp = float(timestamp)

        # test timestamp
        if timestamp < self._starttime:
            self._starttime = timestamp
        if timestamp > self._endtime:
            self._endtime = timestamp

        # check host
        if host:
            self._requests += 1
            self.inc_dict(self._hosts, host)

            # test if it is an upload
            if host == "upload.wikimedia.org":
                upload = path.split("/", 2)[1]
                if upload.lower() == "wikipedia":
                    lang = ""
                    try:
                        lang = path.split("/", 3)[2]
                    except:
                        pass
                    upload = "/".join([upload.lower(), lang.lower()])
                self.inc_dict(self._uploads, upload)
                if "thumb" in path.split("/"):
                    self.inc_dict(self._thumbs_host, upload)
                    self._thumbs.send(url)
                    self._thumbs_set.add(url)
                else:
                    self.inc_dict(self._images_host, upload)
                    self._images.send(url)
                    self._images_set.add(url)
            else:
                self._pages.send(url)

            # increase method counter
            self.inc_dict(self._methods, method)

            # increase request per seconds counter
            self.inc_dict(self._rps, str(int(timestamp)))

        else:
            self._errors.append(line)

    def stats(self):
        """Write statistics."""
        with open(self._filename + ".stats", "w") as output:
            sformat = "%30s: %s\n"
            output.write("[GENERAL]\n")
            output.write(sformat % ("tracefile", self._filename))
            output.write(sformat % ("start time",
                time.strftime("%a, %d %b %Y %H:%M:%S +0000",
                time.gmtime(self._starttime))))
            output.write(sformat % ("end time",
                time.strftime("%a, %d %b %Y %H:%M:%S +0000",
                time.gmtime(self._endtime))))
            output.write("%30s: %.3f sec\n" % ("duration",
                self._endtime - self._starttime))
            output.write(sformat % ("lines", str(self._lines)))
            output.write(sformat % ("requests", str(self._requests)))
            output.write(sformat % ("errors", str(len(self._errors))))

            sformat = "%30s: %8d\n"

            output.write("\n[HOSTS]\n")
            self.print_dict(self._hosts, output)

            output.write("\n[UPLOADS]\n")
            self.print_dict(self._uploads, output)

            output.write("\n[IMAGES]\n")
            self.print_dict(self._images_host, output)
            output.write(sformat % ("files", len(self._images_set)))

            output.write("\n[THUMBS]\n")
            self.print_dict(self._thumbs_host, output)
            output.write(sformat % ("files", len(self._thumbs_set)))

            output.write("\n[METHODS]\n")
            self.print_dict(self._methods, output)

            output.write("\n[ERRORS]\n")
            for error in self._errors:
                output.write(error + "\n")

    def plot(self):
        """Plot statistics."""
        data = ["%d %d" % (int(second) - int(self._starttime), count)
                for second, count in sorted(self._rps.items())]
        title = os.path.splitext(os.path.basename(self._filename))[0]
        gnuplot(title=title, data=data, filename=self._filename,
                ylabel="requests", xlabel="second", using="1:2",
                styles=["points lt 3 pt 5 ps 0.75"])

    @staticmethod
    def get_special_file(filename, special):
        (path, ext) = os.path.splitext(filename)
        return ("." + special).join([path, ext])

    def run(self):
        pagefile = WikiAnalyser.get_special_file(self._filename, "page")
        imagefile = WikiAnalyser.get_special_file(self._filename, "image")
        thumbfile = WikiAnalyser.get_special_file(self._filename, "thumb")

        pfr = FileWriter(pagefile, openfunc=self._openfunc,
                timeout=self._timeout)
        self._pages = pfr.pipe
        pfr.start()
        ifr = FileWriter(imagefile, openfunc=self._openfunc,
                timeout=self._timeout)
        self._images = ifr.pipe
        ifr.start()
        tfr = FileWriter(thumbfile, openfunc=self._openfunc,
                timeout=self._timeout)
        self._thumbs = tfr.pipe
        tfr.start()
        TraceAnalyser.run(self)
        self._pages.send(None)
        self._pages.close()
        self._log.debug("Send done message to pages FileWriter")
        self._images.send(None)
        self._images.close()
        self._log.debug("Send done message to images FileWriter")
        self._thumbs.send(None)
        self._thumbs.close()
        self._log.debug("Send done message to thumbs FileWriter")
        pfr.join()
        ifr.join()
        tfr.join()


class TraceFilter(PipeReader):
    """A filter for traces."""

    def __init__(self, filename, regex, analyse=False, timeout=None):
        PipeReader.__init__(self, timeout)
        self._filename = filename
        self._regex = re.compile(regex)
        self._analyse = analyse
        self._log.debug("Tracefilter for %s created" % filename)

    def consume(self, line):
        """Filter line from tracefile."""
        if self._regex.search(line):
            self.process(line)

    def run(self):
        """Run filter process."""
        self._log.info("Tracefilter started")
        PipeReader.run(self)
        self._log.info("Tracefilter finished")

    def process(self, line):
        """Process filterd line from tracefile."""
        pass


class WikiFilter(TraceFilter):
    """A filter for wikipedia traces from wikibench.eu."""

    DEFAULT_REGEX = r'|'.join([r'http://en.wikipedia.org',
    r'http://upload.wikimedia.org/wikipedia/commons/',
    r'http://upload.wikimedia.org/wikipedia/en/'])

    def __init__(self, filename, host, interval, regex=None, analyse=False,
            openfunc=open, timeout=None):
        self._host = "http://" + host
        self._interval = interval
        self._filterfile = WikiFilter.get_filterfile(filename, interval)
        self._rewritefile = WikiFilter.get_rewritefile(filename, interval)
        self._openfunc = openfunc
        if regex is None:
            regex = WikiFilter.DEFAULT_REGEX
        TraceFilter.__init__(self, filename, regex, analyse, timeout)

    @staticmethod
    def get_filterfile(filename, interval):
        (path, ext) = os.path.splitext(filename)
        return "%s.%d-%d%s" % (path, interval[0], interval[1], ext)

    @staticmethod
    def get_rewritefile(filename, interval):
        (path, ext) = os.path.splitext(filename)
        return "%s.%d-%d.rewrite%s" % (path, interval[0], interval[1], ext)

    def consume(self, line):
        """Filter line from tracefile."""
        (nr, timestamp, url, method) = line.split(" ")
        timestamp = float(timestamp)
        if (timestamp >= self._interval[0] and
            timestamp < self._interval[1] + 1 and
            self._regex.match(url)):
            self.process(line)

    def process(self, line):
        """Process filter line from tracefile."""
        (nr, timestamp, url, method) = line.split(" ")

        # accept only gets
        if method != "-":
            return

        self._filter.send(line)
        if self._analyse:
            self._analyser.send(line)

        # write line in filtered tracefile
        url = re.sub("^http://en.wikipedia.org/wiki/", self._host + "/wiki/",
                url)
        url = re.sub("^http://en.wikipedia.org/w/", self._host + "/w/", url)
        url = re.sub("^http://en.wikipedia.org/", self._host + "/w/", url)
        url = re.sub("^http://upload.wikimedia.org/wikipedia/[a-z]+/",
                self._host + "/w/images/", url)

        line = " ".join([nr, timestamp, url, method])

        self._rewrite.send(line)

    def run(self):
        filterfw = FileWriter(self._filterfile, openfunc=self._openfunc,
                timeout=self._timeout)
        self._filter = filterfw.pipe
        filterfw.start()
        rewritefw = FileWriter(self._rewritefile, openfunc=self._openfunc,
                timeout=self._timeout)
        self._rewrite = rewritefw.pipe
        rewritefw.start()

        if self._analyse:
            analyser = WikiAnalyser(self._filterfile, self._openfunc,
                    self._timeout)
            self._analyser = analyser.pipe
            analyser.start()

        TraceFilter.run(self)

        self._filter.send(None)
        self._filter.close()
        self._log.debug("Send done message to filter FileWriter")
        self._rewrite.send(None)
        self._rewrite.close()
        self._log.debug("Send done message to rewrite FileWriter")

        if self._analyse:
            self._analyser.send(None)
            self._analyser.close()
            self._log.debug("Send done message to filterd Analyser")
            analyser.join()

        filterfw.join()
        rewritefw.join()


class FileCollector(PipeReader):
    """docstring for FileCollector"""

    def __init__(self, download_dir, copy_dir, regex=None, port=80, async=25,
            retry=7, timeout=None):
        PipeReader.__init__(self, timeout)
        self._download_dir = os.path.abspath(download_dir)
        self._copy_dir = os.path.abspath(copy_dir)
        self._downloads = []
        if regex is None:
            regex = WikiAnalyser.DEFAULT_REGEX
        self._regex = regex
        self._port = port
        self._async = async
        self._retry = retry
        self._crawler = dict()

    def get_filename(self, url):
        path = re.sub(self._regex, "", url)
        return os.path.join(self._download_dir, path)

    def copy_file(self, filename):
        try:
            target = filename.replace(self._download_dir, self._copy_dir)
            dirname = os.path.dirname(target)
            if not os.path.isdir(dirname):
                os.makedirs(dirname)
                self._log.debug("Create directory %s" % dirname)
            shutil.copy(filename, target)
            self._log.debug("Copy file %s to %s" % (filename, target))
        except Exception, e:
            self._log.error("Unable to copy file %s (%s)" % (filename, e))

    def consume(self, url):
        url = urllib.unquote(url)
        filename = self.get_filename(url)
        if os.path.isfile(filename):
            self._log.debug("File %s already exists at %s" % (url, filename))
            self.copy_file(filename)
        else:
            split = urlparse.urlsplit(url)
            host = split.hostname
            path = split.path
            if host not in self._crawler:
                self._crawler[host] = FileCrawler(host, self._download_dir,
                        self._port, self._async, self._retry, self._timeout)
                self._crawler[host].start()
            self._log.debug("Send %s path to FileCrawler for host %s" %
                    (path, host))
            self._crawler[host].pipe.send(path)
            self._downloads.append(filename)

    def run(self):
        PipeReader.run(self)
        for crawler in self._crawler.values():
            crawler.pipe.send(None)
        for crawler in self._crawler.values():
            crawler.join()
        for filename in self._downloads:
            if os.path.isfile(filename):
                self.copy_file(filename)
