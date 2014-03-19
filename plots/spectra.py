"""
Tools for plotting and comparing spectra.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
from radmap import analyze

def downsample(hist, start, end, step):
    """Downsample a histogram by summing up values in wider bins."""
    down = []
    for i in range(start, end, step):
        down.append(np.sum(hist[i:i+step]))

    return down

def plot_histograms(hists, title=None):
    """Plot a set of histograms given as (filename, label) tuples
    
    Files should be CSVs readable with np.loadtxt, delimited by commas.
    Histogram data should be using bin counts, and should have 4096 bins.
    """

    data = map(lambda f: (np.loadtxt(f[0], delimiter=","), f[1]), hists)
    
    energies = map(analyze.binToEnergy, range(2000))[10:2000:5]
    
    downsampledHists = []
    for hist in data:
        ds = downsample(hist[0], 10, 2000, 5)
        downsampledHists.append((np.divide(ds, np.sum(ds)), hist[1]))
    
    ax = plt.subplot(111)
    if title is not None:
        ax.set_title(title)
    
    ax.xaxis.set_major_locator(MultipleLocator(200))
    ax.xaxis.set_minor_locator(MultipleLocator(50))
    
    for hist in downsampledHists:
        plt.plot(energies, hist[0], label=hist[1])
    
    plt.xlabel("Energy (keV)")
    plt.ylabel("Count density")
    plt.legend()
    plt.show()
