"""
Tools to build bihistograms of D^2 statistics.
"""
import numpy as np
import scipy.stats
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

def bihist(y1, y1label, y2, y2label, nbins=10, h=None):
    '''
    Bihistogram.
    h is an axis handle. If not present, a new figure is created.
    '''
    def yaxisfmt(y, pos):
        return "%0.2f" % np.abs(y)

    if h is None: h = plt.figure().add_subplot(111)
    xmin = scipy.floor(scipy.minimum(y1.min(), y2.min()))
    xmax = scipy.ceil(scipy.maximum(y1.max(), y2.max()))
    bins = scipy.linspace(xmin, xmax, nbins)
    h.yaxis.set_major_formatter(FuncFormatter(yaxisfmt))
    n1, bins1, patch1 = h.hist(y1, bins, normed=True, alpha=0.8, label=y1label)
    n2, bins2, patch2 = h.hist(y2, bins, normed=True, alpha=0.8, label=y2label)
    # set ymax:
    ymax = 0
    for i in patch1:
        height = i.get_height()
        if height > ymax: ymax = height
    # invert second histogram and set ymin:
    ymin = 0
    for i in patch2:
        height = i.get_height()
        height = -height
        i.set_height(height)
        if height < ymin: ymin = height
    h.set_ylim(ymin*1.1, ymax*1.1)
    h.figure.canvas.draw()

def distHist(source1, source2):
    """Produce a bihistogram comparing D^2 for two different methods.
    
    Also adds p-value tick labels and the theoretical chi-squared distribution.

    source1, source2: tuples whose first entry is a filename
    containing D^2 data (as a CSV) and whose second entry is its name for the
    legend.
    """
    s1 = np.loadtxt(source1[0], delimiter=",")
    s2 = np.loadtxt(source2[0], delimiter=",")

    x = np.linspace(0, 100, num=200)

    fig = plt.figure()
    ax1 = fig.add_subplot(111)
    ax2 = ax1.twiny()

    bihist(s1[s1 < 120], source1[1], s2[s2 < 120], source2[1], 100, h=ax1)
    plt.plot(x, scipy.stats.chi2(7).pdf(x), 'k', axes=ax1)
    plt.plot(x, -scipy.stats.chi2(7).pdf(x), 'k', axes=ax1)

    p_ticks = scipy.stats.chi2(7).isf(np.power(10.0, -np.arange(3, 15, 3)))
    ax2.set_xticks(p_ticks)
    ax2.set_xticklabels(["$10^{-3}$", "$10^{-6}$", "$10^{-9}$", "$10^{-12}$", "$10^{-15}$"])

    ax1.set_xlabel("$D^2$")
    ax2.set_xlabel("p value")
    ax1.set_ylabel("Density")
    ax1.legend()
    plt.show()
    
    return (scipy.stats.mstats.mquantiles(s1, [0.99]),
            scipy.stats.mstats.mquantiles(s2, [0.99]))
