#TODO: This module is too slow. It needs to restructured.

import numpy as np
import scipy as sp
import scipy.io as io
import math

# Bins chosen so that each roughly contains the same number of counts
EQUAL_BINS = [(85, 102), (102, 121), (121, 145), (145, 176),
              (176, 223), (223, 314), (314, 544), (544, 2500)]

# Estimated average overdispersion for the chosen bins
DISPERSION = 1.31

try:
    corr = io.loadmat("correlation.mat")
    scr_corr = corr["scr"]
    bin_corr = corr["bin"]
except IOError:
    # If the correlation matrix doesn't exist, warn the user but proceed --
    # they might be running correlate.py to generate a new one
    print "No stored correlation matrices found!"

def nscrad(histogram, T, invBgCov):
    """Calculate N-SCRAD statistic for given histogram and T, the background spectral
       shape matrix. This is the Mahalanobis distance metric. s is scaled by the
       number of counts in the first bin to make this scale-invariant."""
    s = np.dot(T, histogram)
    return s, np.dot(np.dot(np.transpose(s), invBgCov), s)

def downsampleHistogram(histogram, bins):
    """Take a histogram of a large number of bins and downsample it into a smaller number of bins.
       The variable "bins" must contain a list of tuples with the bin bounds.
    """
    downsampled = np.zeros(len(bins))

    i = 0
    for bin in bins:
        downsampled[i] = np.sum(histogram[bin[0] : bin[1]])
        i += 1

    return downsampled

def getShapeMatrix(histogram):
    """Get the matrix T_alpha, representing the spectral shape of the given histogram.
    """
    bins = len(histogram)
    T = np.zeros((bins - 1, bins))

    histogram = np.clip(histogram, 1, float("+inf"))

    for i in range(1, bins):
        T[i - 1][i] = - float(histogram[0]) / float(histogram[i])
        T[i - 1][0] = 1

    return T

def sqrtBinSizes(startBinWidth, numBins, startBin):
    """Create a list of bin boundary tuples where bin sizes are proportional to the
       square root of their lower bound. The lowest bin starts at startBin, allowing
       the discard of low-energy data. Square root spacing gives smaller bins for the
       low-energy portion of the spectrum, where all the interesting stuff happens."""
    bins = []
    i = 0
    for i in range(numBins):
        width = startBinWidth * math.sqrt(startBin + 1)
        bins.append((int(math.floor(startBin)), int(math.floor(startBin + width))))
        startBin += width

    return bins

def sumHistograms(hists):
    """Take a list of histograms and sum them element-wise, giving a combined
       total histogram which includes all the observations for all bins.
       Expects each histogram to be the first element in a tuple, since that's
       how Psycopg2 presents the data."""

    def adder(x, y):
        if isinstance(x, tuple):
            x = x[0]
        if isinstance(y, tuple):
            y = y[0]
        return np.add(x, y)
    return reduce(adder, hists)

def makeCovMat(oldHist, hist, oldTime, newTime, overDisperse=1):
    """Build an estimated covariance matrix using new and old spectral observations.

    Optional overDisperse parameter handles the case that var(c_i) = C c_i,
    where C is some constant greater than one, by inflating the estimated
    standard deviations.

    Returns None if the standard deviations come out negative.
    """
    stds = np.array([hist[0] + (oldHist[0] / oldHist[i])**2 * hist[i] -
                     2.0 * oldHist[0] * math.sqrt(oldHist[0] * oldHist[i]) *
                     (newTime / oldTime)**2 * bin_corr[0, i] / oldHist[i]
                     for i in range(1, len(hist))]) * overDisperse

    if len(stds[stds < 0]) > 0:
        return None

    stds[stds < 1] = 1
    stds = np.sqrt(stds)

    cov = np.zeros_like(scr_corr)
    for i in range(scr_corr.shape[0]):
        for j in range(scr_corr.shape[1]):
            cov[i,j] = scr_corr[i,j] * stds[i] * stds[j]

    return cov

#TODO: Speed Up
def SCRRegion(cur, xbounds, ybounds, times, obsTime, bins, srid=3663,
              overDisperse=1):
    """Compute SCR by using precomputed correlation matrix."""

    if obsTime is None:
        return (None, None, np.zeros(len(bins) - 1), np.zeros(4096))

    cur.execute("SELECT histogram FROM histograms " +
                "WHERE ST_Contains(ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, %s), 4326), location) " +
                "AND time > %s AND time < %s",
                (xbounds[0], ybounds[0], xbounds[1], ybounds[1], srid, times[0], times[1]))
    if cur.rowcount == 0:
        return (None, None, np.zeros(len(bins) - 1), np.zeros(4096))

    histogram = sumHistograms(cur)

    cur.execute("SELECT histogram, sampletime FROM histograms " +
                "WHERE ST_Contains(ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, %s), 4326), location) " +
                "AND time < %s ORDER BY time DESC limit %s",
                (xbounds[0], ybounds[0], xbounds[1], ybounds[1], srid, times[0], 10000))

    # Fetch enough past data to make 15 times the current observation time,
    # at most. Since the background spectrum can slowly change, we don't want
    # to use the entire background dataset.
    time = 0
    oldHist = np.zeros(len(bins))
    for row in cur:
        oldHist = np.add(oldHist, downsampleHistogram(row[0], bins))
        time += row[1]
        if time / obsTime > 15.0:
            break

    # Require at least twice as much background data as new data, for a firm comparison.
    # Don't allow old bins to be zero, since that causes division by zero.
    if time / obsTime < 2.0 or len(oldHist[oldHist == 0]) > 0:
        return (None, None, np.zeros(len(bins) - 1), histogram)

    hist = downsampleHistogram(histogram, bins)

    cov = makeCovMat(oldHist, hist, time, obsTime, overDisperse)
    if cov is None:
        return (None, None, np.zeros(len(bins) - 1),  histogram)

    T = getShapeMatrix(oldHist)

    scrs, S = nscrad(hist, T, sp.linalg.inv(cov))
    p = sp.stats.chi2.sf(S, len(bins) - 1)

    return (p, S, scrs, histogram)

def make_grid(cur, start, end, stepsize, srid = 4326):
    """Produce a spatial meshgrid covering data collected between start and
    end, with specified grid cell size and SRID.

    Returns (xx, yy)."""

    cur.execute("SELECT ST_Extent(ST_Transform(location, %s)) FROM histograms " +
                "WHERE time > %s AND time < %s AND hdop > 0", (srid, start, end))

    box = cur.fetchone()
    if box[0] is None:
        return (None, None)

    box = box[0][4:-1].split(',')
    bottomleft = map(float, box[0].split(' '))
    topright = map(float, box[1].split(' '))

    xx = np.arange(bottomleft[0], topright[0] + stepsize, step=stepsize)
    yy = np.arange(bottomleft[1], topright[1] + stepsize, step=stepsize)

    xx, yy = np.meshgrid(xx, yy)
    return xx, yy
