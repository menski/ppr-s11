'''
File: trace.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Basic classes for trace handling.
'''

from basic import PipeReader, FileWriter, Process
import multiprocessing
import sys
import subprocess
import re
import time
import os.path
from operator import itemgetter


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

    def __init__(self, filename, timeout=PipeReader.DEFAULT_TIMEOUT):
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

    HOST_REGEX = r'http://(([\w-]+\.)*\w+)/'
    HOST_PATTERN = re.compile(HOST_REGEX)
    UPLOAD_REGEX = r'http://upload.wikimedia.org/([\w\.]+/?)?'
    UPLOAD_PATTERN = re.compile(UPLOAD_REGEX)
    WIKIUPLOAD_REGEX = r'http://upload.wikimedia.org/wikipedia/([\w\.]+/?)?'
    WIKIUPLOAD_PATTERN = re.compile(WIKIUPLOAD_REGEX)
    THUMB_REGEX = r'|'.join([UPLOAD_REGEX + "thumb/",
        WIKIUPLOAD_REGEX + "thumb/"])
    THUMB_PATTERN = re.compile(THUMB_REGEX)

    def __init__(self, filename, openfunc=open,
            timeout=PipeReader.DEFAULT_TIMEOUT):
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
        uniq = 0
        for key, value in sorted(dictonary.items(), key=itemgetter(1),
            reverse=True):
            sum += value
            uniq += 1
            output.write(sformat % (key, value))
        output.write("%40s\n" % "----------")
        output.write(sformat % ("sum", sum))
        output.write(sformat % ("uniq", uniq))

    def consume(self, line):
        """Analyse a trace line."""
        self._lines += 1

        # split line
        try:
            (nr, timestamp, url, method) = line.split(" ")
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

        # parse host
        m = WikiAnalyser.HOST_PATTERN.match(url)
        if m:
            self._requests += 1
            self.inc_dict(self._hosts, m.group(1))

            # test if it is an upload
            m = WikiAnalyser.UPLOAD_PATTERN.match(url)
            if m:
                upload = m.group(1)
                if upload is None:
                    upload = ""
                if upload.lower() == "wikipedia/":
                    lang = WikiAnalyser.WIKIUPLOAD_PATTERN.match(url)
                    if lang:
                        if lang.group(1) is None:
                            lang = ""
                        else:
                            lang = lang.group(1)
                        upload = "".join(
                                [upload.lower(), lang.lower()])
                self.inc_dict(self._uploads, upload)
                if WikiAnalyser.THUMB_PATTERN.match(url):
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

    def run(self):
        (path, ext) = os.path.splitext(self._filename)
        pagefile = ".page".join([path, ext])
        imagefile = ".image".join([path, ext])
        thumbfile = ".thumb".join([path, ext])

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

    def __init__(self, filename, regex, analyse=False,
            timeout=PipeReader.DEFAULT_TIMEOUT):
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
            openfunc=open, timeout=PipeReader.DEFAULT_TIMEOUT):
        self._host = "http://" + host
        self._interval = interval
        (path, ext) = os.path.splitext(filename)
        self._filterfile = "%s.%d-%d%s" % (path, interval[0], interval[1],
                ext)
        self._rewritefile = "%s.%d-%d.rewrite%s" % (path, interval[0],
                interval[1], ext)
        self._openfunc = openfunc
        if regex is None:
            regex = WikiFilter.DEFAULT_REGEX
        TraceFilter.__init__(self, filename, regex, analyse, timeout)

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
