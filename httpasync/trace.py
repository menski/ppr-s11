'''
File: trace.py
Author: Sebastian Menski
E-Mail: sebastian.menski@googlemail.com'
Description: Collection of classes and functions to analyze webserver traces.
'''

import subprocess


def gnuplot(title, data, filename, ylabel=None, xlabel=None, using=None,
        style=None):
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
            stdin.write('set ylabel "%s"\n' % xlabel)

        # set grid
        stdin.write('set grid y\n')

        # create plot command
        plotcmd = 'plot "-"'
        if using is not None:
            plotcmd = " ".join([plotcmd, "using", using])
        plotcmd = " ".join([plotcmd, "notitle"])
        if style is not None:
            plotcmd = " ".join([plotcmd, "with", style])
        stdin.write(plotcmd + "\n")

        # data input
        for line in data:
            stdin.write(line + "\n")
        stdin.write("e\n")

        # quit process
        stdin.write("quit\n")
        return gnuplot.wait()


def readfile(filename, process, openfunc=open):
    """
    Read a file and process it by given function.

    Arguments:
    - `filename`    : filename to read
    - `process`     : function to process lines
    - `openfunc`    : function to open file (i.e. gzip.open)

    """
    with openfunc(filename, mode="rb") as file:
        for line in file:
            process(line.strip())
