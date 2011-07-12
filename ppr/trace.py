'''
File: trace.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Basic classes for trace handling.
'''

from basic import Process
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


class TraceAnalyser(Process):
    """Analyse a trace and output.write(some statitics"""

    DONE = "###DONE###"

    def __init__(self, queue=multiprocessing.Queue(), plot=False, write=False):
        Process.__init__(self)
        self._queue = queue
        self._plot = plot
        self._write = write
        self._gnuplot = gnuplot
        self._done = False
        self.init()

    def init(self):
        """Initialize the analyzier."""
        pass

    def add(self, line):
        """Add a trace line to queue."""
        self._queue.put(line)

    def done(self):
        """Add done message to queue."""
        self._queue.put(TraceAnalyser.DONE)

    def analyse(self, line):
        """Analyse a trace line."""
        pass

    def stats(self):
        """Write statistics."""
        pass

    def plot(self):
        """Plot statistics."""
        pass

    def write(self):
        """Write special files."""
        pass

    def run(self):
        """Run analyse process."""
        while not self._done or not self._queue.empty():
            if not self._queue.empty:
                line = self._queue.get()
                if line == TraceAnalyser.DONE:
                    self._done = True
                else:
                    self.analyse(line)
            else:
                time.sleep(1)
        self.stats()
        if self._plot:
            self.plot()
        if self._write:
            self.write()


class WikiAnalyser(TraceAnalyser):
    """Analyse a wiki trace from wikibench.eu"""

    HOST = re.compile(r'http://(([\w-]+\.)*\w+)/')
    UPLOAD_REGEX = r'http://upload.wikimedia.org/([\w\.]+/?)?'
    UPLOAD = re.compile(UPLOAD_REGEX)
    WIKIUPLOAD_REGEX = r'http://upload.wikimedia.org/wikipedia/([\w\.]+/?)?'
    WIKIUPLOAD = re.compile(WIKIUPLOAD_REGEX)
    THUMB = re.compile(r'|'.join([UPLOAD_REGEX + "thumb/",
        WIKIUPLOAD_REGEX + "thumb/"]))

    def init(self):
        """Initialize the analyser."""
        self._lines = 0
        self._requests = 0
        self._errors = []
        self._starttime = time.time()
        self._endtime = 0
        self._hosts = dict()
        self._uploads = dict()
        self._pages = set()
        self._images = set()
        self._images_host = dict()
        self._thumbs = set()
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

    def analyse(self, line):
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
        m = WikiAnalyser.HOST.match(url)
        if m:
            self._requests += 1
            self.inc_dict(self._hosts, m.group(1))

            # test if it is an upload
            m = WikiAnalyser.UPLOAD.match(url)
            if m:
                upload = m.group(1)
                if upload is None:
                    upload = ""
                if upload.lower() == "wikipedia/":
                    lang = WikiAnalyser.WIKIUPLOAD.match(url)
                    if lang:
                        if lang.group(1) is None:
                            lang = ""
                        else:
                            lang = lang.group(1)
                        upload = "".join(
                                [upload.lower(), lang.lower()])
                self.inc_dict(self._uploads, upload)
                if WikiAnalyser.THUMB.match(url):
                    self.inc_dict(self._thumbs_host, upload)
                    self._thumbs.add(url)
                else:
                    self.inc_dict(self._images_host, upload)
                    self._images.add(url)
            else:
                self._pages.add(url)

            # increase method counter
            self.inc_dict(self._methods, method)

            # increase request per seconds counter
            self.inc_dict(self._rps, str(int(timestamp)))

        else:
            self._errors.append(line)

    def stats(self):
        """Write statistics."""
        with open(self._tracefile + ".stats", "wb") as output:
            sformat = "%30s: %s\n"
            output.write("[GENERAL]\n")
            output.write(sformat % ("tracefile", self._tracefile))
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
            output.write(sformat % ("files", len(self._images)))

            output.write("\n[THUMBS]\n")
            self.print_dict(self._thumbs_host, output)
            output.write(sformat % ("files", len(self._thumbs)))

            output.write("\n[METHODS]\n")
            self.print_dict(self._methods, output)

            output.write("\n[ERRORS]\n")
            for error in self._errors:
                output.write(error + "\n")

    def plot(self):
        """Plot statistics."""
        data = ["%d %d" % (int(second) - int(self._starttime), count)
                for second, count in sorted(self._rps.items())]
        title = os.path.splitext(os.path.basename(self._tracefile))[0]
        gnuplot(title=title, data=data, filename=self._tracefile,
                ylabel="requests", xlabel="second", using="1:2",
                styles=["points lt 3 pt 5 ps 0.75"])

    def write(self):
        """Write page, image and thumb list."""
        (path, ext) = os.path.splitext(self._tracefile)
        pagefile = ".page".join([path, ext])
        imagefile = ".image".join([path, ext])
        thumbfile = ".thumb".join([path, ext])

        self.writefile(pagefile, self._pages)
        self.writefile(imagefile, self._images)
        self.writefile(thumbfile, self._thumbs)

    def writefile(self, filename, content):
        output = self._openfunc(filename, "wb")
        try:
            for url in content:
                output.write(url + "\n")
        finally:
            output.close()


class TraceFilter(Process):
    """A filter for traces."""

    DONE = "###DONE###"

    def __init__(self, regex, queue=multiprocessing.Queue()):
        self._regex = re.compile(regex)
        self._queue = queue

    def add(self, line):
        """Add trace line to queue."""
        self._queue.put(line)

    def done(self):
        """Add done message to queue."""
        self._queue.put(TraceFilter.DONE)

    def run(self):
        """Run filter process."""
        while not self._done or not self._queue.empty():
            if not self._queue.empty():
                line = self._queue.get()
                if line == TraceFilter.DONE:
                    self._done = True
                else:
                    self.filter(line)
            else:
                time.sleep(1)

    def filter(self, line):
        """Filter line from tracefile."""
        if self._regex.search(line):
            self.process(line)

    def process(self, line):
        """Process filterd line from tracefile."""
        pass


class WikiFilter(TraceFilter):
    """A filter for wikipedia traces from wikibench.eu."""

    def __init__(self, tracefile, host, interval, regex, openfunc=open,
            queue=multiprocessing.Queue()):
        self._host = "http://" + host
        self._interval = interval
        (path, ext) = os.path.splitext(tracefile)
        self._filterfile = "%s.%d-%d%s" % (path, interval[0], interval[1],
                ext)
        self._rewritefile = "%s.%d-%d.rewrite%s" % (path, interval[0],
                interval[1], ext)
        self._filter = openfunc(self._filterfile, "wb")
        self._rewrite = openfunc(self._rewritefile, "wb")
        TraceFilter.__init__(self, tracefile, regex, openfunc)
        self._filter.close()
        self._rewrite.close()

    def get_filename(self):
        return self._filterfile

    def filter(self, line):
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

        self._filter.write(line + "\n")

        # write line in filtered tracefile
        url = re.sub("^http://en.wikipedia.org/wiki/", self._host + "/wiki/",
                url)
        url = re.sub("^http://en.wikipedia.org/w/", self._host + "/w/", url)
        url = re.sub("^http://en.wikipedia.org/", self._host + "/w/", url)
        url = re.sub("^http://upload.wikimedia.org/wikipedia/[a-z]+/",
                self._host + "/w/images/", url)

        line = " ".join([nr, timestamp, url, method])

        self._rewrite.write(line + "\n")
