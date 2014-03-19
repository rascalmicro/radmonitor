# Batch data analysis. Run a function over each data run.
from datetime import timedelta, tzinfo, datetime
import multiprocessing, analyze, psycopg2, nscrad, math
import numpy as np
from scipy import stats
import scipy as sp
import scipy.io as io
from util.CST import cst

# Divide days into two intervals, marked by dividers.
dividers = [datetime(2012, 7, 1, 0, 0, 0, 0, cst),
            datetime(2012, 7, 15, 0, 0, 0, 0, cst)]
delta = timedelta(15)
end = datetime(2012, 8, 4, 0, 0, 0, 0, cst)

def SCRs_date(times):
    """Get a list of SCRs in grid squares in a region for a given time period.

    Watch out for July 12, when I foolishly put the detector against the wall
    of the PETEX building and introduced a huge spectral anomaly."""

    conn = psycopg2.connect(database = "radiation", user = "radiation",
                            password = "radiation", host = "localhost")
    cur = conn.cursor()

    binsize = 250
    start, end = times

    xx, yy = nscrad.make_grid(cur, start, end, binsize, 3663)
    bins = nscrad.EQUAL_BINS

    if xx is None or yy is None:
        return None

    scrs = []

    for i in range(xx.shape[0] - 1):
        for j in range(xx.shape[1] - 1):
            cur.execute("SELECT sum(sampletime) FROM histograms " +
                        "WHERE ST_Contains(ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 3663), 4326), location) " +
                        "AND time > %s AND time < %s",
                        (xx[i,j], yy[i,j], xx[i,j+1], yy[i+1,j], start, end))
            sampleTime = cur.fetchone()[0]

            _, S, _, _ = nscrad.SCRRegion(cur, [xx[i,j], xx[i,j+1]],
                                          [yy[i,j], yy[i+1,j]], [start, end],
                                          sampleTime, bins,
                                          overDisperse=nscrad.DISPERSION)

            if S is None:
                continue

            scrs.append(S)
    return scrs

def SCRs_date_reduce(scrs):
    return sum(filter(lambda p: p is not None, scrs), [])

def spatial_SCR(times):
    """Run a spatial SCR: compare cells to fixed reference cell, rather than to
       past data."""
    conn = psycopg2.connect(database = "radiation", user = "radiation",
                            password = "radiation", host = "localhost")
    cur = conn.cursor()

    binsize = 250
    start, end = times

    xx, yy = nscrad.make_grid(cur, start, end, binsize, 3663)
    bins = nscrad.EQUAL_BINS

    if xx is None or yy is None:
        return None

    # Use ARL as reference.
    # The coordinates given are a fixed 250m cell containing ARL.
    cur.execute("SELECT histogram FROM histograms " +
                "WHERE ST_Contains(ST_MakeEnvelope(%s, %s, %s, %s, 3663), ST_Transform(location, 3663)) " +
                "AND time > %s AND time < %s",
                (950495.93852436, 3082419.737539, 950745.93852436,
                 3082669.737539, start, end))
    if cur.rowcount == 0:
        return None

    oldHist = nscrad.sumHistograms(map(lambda h: nscrad.downsampleHistogram(h[0], bins),
                                   cur))
    oldTime = cur.rowcount * 2

    T = nscrad.getShapeMatrix(oldHist)
    scrs = []

    for i in range(xx.shape[0] - 1):
        for j in range(xx.shape[1] - 1):
            cur.execute("SELECT sum(sampletime) FROM histograms " +
                        "WHERE ST_Contains(ST_MakeEnvelope(%s, %s, %s, %s, 3663), ST_Transform(location, 3663)) " +
                        "AND time > %s AND time < %s",
                        (xx[i,j], yy[i,j], xx[i,j+1], yy[i+1,j], start, end))
            sampleTime = cur.fetchone()[0]
            if sampleTime is None:
                continue

            cur.execute("SELECT histogram FROM histograms " +
                        "WHERE ST_Contains(ST_MakeEnvelope(%s, %s, %s, %s, 3663), ST_Transform(location, 3663)) " +
                        "AND time > %s AND time < %s",
                        (xx[i,j], yy[i,j], xx[i,j+1], yy[i+1,j], start, end))
            hist = nscrad.sumHistograms(map(lambda h: nscrad.downsampleHistogram(h[0], bins),
                                               cur))
            if np.sum(oldHist) < np.sum(hist) * 2:
                continue

            cov = nscrad.makeCovMat(oldHist, hist, oldTime, sampleTime,
                                    overDisperse=nscrad.DISPERSION)
            ss, S = nscrad.nscrad(hist, T, sp.linalg.inv(cov))

            scrs.append(S)
    return scrs

def poisson_dispersion(times):
    """Run a Poisson dispersion test on bin count rates. Return p.

    http://www.stats.uwo.ca/faculty/aim/2004/04-259/notes/DispersionTests.pdf
    """

    conn = psycopg2.connect(database = "radiation", user = "radiation",
                            password = "radiation", host = "localhost")
    cur = conn.cursor()
    
    binsize = 125
    start, end = times

    xx, yy = nscrad.make_grid(cur, start, end, binsize, 3663)
    bins = nscrad.EQUAL_BINS

    if xx is None or yy is None:
        return None

    ps =  []

    for i in range(xx.shape[0] - 1):
        for j in range(xx.shape[1] - 1):
            cur.execute("SELECT histogram FROM histograms " +
                        "WHERE ST_Contains(ST_MakeEnvelope(%s, %s, %s, %s, 3663), ST_Transform(location, 3663)) " +
                        "AND time > %s AND time < %s",
                        (xx[i,j], yy[i,j], xx[i,j+1], yy[i+1,j], start, end))

            cpss = []
            for hist in cur:
                cps = nscrad.downsampleHistogram(hist[0], bins)
                cpss.append(cps)
            if len(cpss) < 15:
                continue
            # Option one: variance-to-mean ratio
            ps.append(np.divide(np.var(cpss, axis=0), np.mean(cpss, axis=0)))

            # Option two: Poisson dispersion test
            #ps.append(stats.chi2.sf(np.divide(np.var(cpss, axis=0) * len(cpss), np.mean(cpss, axis=0)), len(cpss) - 1))

    return ps

def poisson_dispersion_reduce(ps):
    return sum(filter(lambda p: p is not None, ps), [])

if __name__ == "__main__":
    chunks = []
    while True:
        chunks.append((dividers[0], dividers[1]))
        dividers[0] += delta
        chunks.append((dividers[1], dividers[0]))
        dividers[1] += delta
        if dividers[1] > end:
            break

    pool = multiprocessing.Pool()
    data = poisson_dispersion_reduce(pool.map(poisson_dispersion, chunks))

    print ','.join([str(s) for s in list(np.mean(np.array(data), axis=0))])
    #for pt in data:
    #    print pt
