"""
Poisson spatial kriging of count rates.

Methods are derived from results in the following sources:

P. Monestiez, L. Dubroca, E. Bonnin, et al. Geostatistical modelling of 
spatial distribution of Balaenoptera physalus in the Northwestern Mediterranean
Sea from sparse count data and heterogeneous observation efforts. Ecological
Modelling 193 (2006), 615-628. doi:10.1016/j.ecolmodel.2005.08.042

Noel Cressie, Statistics for Spatial Data. Wiley 1993.

Chapter 4 of my thesis (in the `thesis/` directory) also contains a derivation
of the results used here, along with (hopefully) accessible explanations.
"""

import numpy as np
import scipy.linalg as linalg
import psycopg2, nscrad
import scipy.stats

def krige_at(points, times, data, pred_points, cov_func):
    """Perform Poisson kriging on data.

    Can simultaneously predict multiple variables if `data` has more than one
    column; however, each variable is predicted independently, without
    cokriging.

    points: (N,2) ndarray of Euclidean coordinates, one row per observation
    times: (N,1) ndarray; observation time of each observation
    data: (N,M) ndarray of observations at each point
    pred_points: (N,2) ndarray of points at which to predict
    cov_func: function which takes two points and gives a covariance
    
    Returns: (preds, vars)
    where preds is a (N,M) ndarray of predictions and vars a (N,M) ndarray of
    variances.
    """

    N = points.shape[0] # number of data points
    Npreds = pred_points.shape[0] # number of points to predict
    if len(data.shape) > 1:
        M = data.shape[1] # number of variables to independently predict
    else:
        M = 1
    cov_mat = np.ones((N+1, N+1))
    cov_mat[-1, -1] = 0

    # We want to work with count rates rather than total counts
    rates = np.divide(data, times)

    # Estimated count rate variance at a single point
    pred_var = cov_func(np.array([0,0]), np.array([0,0]))

    # m is the weighted average count rate
    m = np.average(rates, axis=0, weights=times[:,0])

    # Build the basic covariance matrix. We add terms to the diagonal later.
    for i in range(cov_mat.shape[0] - 1):
        for j in range(cov_mat.shape[1] - 1):
            cov_mat[i, j] = cov_func(points[i,:], points[j,:])

    # Covariance of data points with prediction points.
    # We use each column one at a time to produce each prediction.
    # Bottom row is ones.
    covs = np.ones((N+1, Npreds))

    for i in range(Npreds):
       for j in range(N):
           covs[j, i] = cov_func(points[j,:], pred_points[i,:])

    preds = np.zeros((Npreds, M))
    vars = np.zeros((Npreds, M))

    for j in range(M):
        diag = np.zeros_like(cov_mat)
        diag[:-1,:-1] = np.diag([m[j] / times[k,0] for k in range(N)])
        cov_mat_lu = linalg.lu_factor(np.add(cov_mat, diag))

        for i in range(Npreds):
            weights = linalg.lu_solve(cov_mat_lu, covs[:, i])
            preds[i, j] = np.dot(weights[:-1], rates[:,j])

            vars[i, j] = pred_var - np.dot(weights[:-1], covs[:-1,i]) - weights[-1]

    return preds, vars

def dist(a, b):
    """Return the Euclidean distance between two points."""
    return np.sqrt(np.sum(np.power(a - b, 2)))

def make_sq_exp(bandwidth, amplitude):
    return make_exp_cov(amplitude, bandwidth, 2)

def make_exp_cov(amplitude, bandwidth, exponent):
    def exp_cov(a, b):
        return amplitude * np.exp(-(dist(a, b) / bandwidth)**exponent)
    return exp_cov

def anomaly_detect(predictions, vars, observed, t):
    """Compare predictions to observed values.

    predictions: column vector of predicted count rates
    vars: column vector of prediction variances
    observed: column vector of observed counts
    t: column vector of observation times for the given counts"""

    a = np.divide(np.power(predictions, 2), vars)
    b = t * np.divide(vars, predictions + t * vars)

    ps = np.min(scipy.stats.nbinom(a, 1-b).sf(observed), axis=1)
    return scipy.stats.beta(1, predictions.shape[1]).cdf(ps)

def determine_p_threshold(ps, fdr):
    """Use the Benjamini-Hochberg procedure to choose alpha.

    ps: a list of observed p values
    fdr: a desired false discovery rate, 0 < fdr < 1

    Returns the lowest p value which should not be rejected among ps; that is,
    all hypotheses with p less than the return value should be rejected.
    """

    sorted = np.sort(ps)

    cmp = fdr * np.arange(1, len(sorted) + 1) / len(sorted)

    not_rejected = sorted > cmp

    if len(not_rejected) > 0:
        return sorted[not_rejected][0]
    else:
        return 1

def variogram(intervals, hs):
    """Estimate an empirical variogram at the given distances.

    intervals is a list of tuples, where each tuple is a (start, end) datetime
    pair. Each interval is treated as an independent observation.
    hs is a list of distances at which the variogram will be estimated. The
    data will be aggregated into spatial bins hs[0] meters on a side.

    Returns an ndarray whose first column is h, second column is the estimated
    variogram, and third column is the number of observation pairs that
    distance apart."""

    conn = psycopg2.connect(database = "radiation", user = "radiation",
                            password = "radiation", host = "localhost")
    cur = conn.cursor()

    # Compute m, the weighted mean count rate
    cur.execute("SELECT sum(cps * sampletime) / sum(sampletime) " +
                "FROM histograms " +
                "WHERE time BETWEEN %s AND %s",
                (intervals[0][0], intervals[-1][1]))
    row = cur.fetchone()
    if row is None:
        return None # no data
    m = row[0]

    data = []
    for start, end in intervals:
        xx, yy = nscrad.make_grid(cur, start, end, hs[0], 3663)

        C = np.zeros((xx.shape[0] - 1, xx.shape[1] - 1))
        t = np.zeros((xx.shape[0] - 1, xx.shape[1] - 1))
        pts = np.zeros((xx.shape[0] - 1, xx.shape[1] - 1, 2))

        for i in range(xx.shape[0] - 1):
            for j in range(xx.shape[1] - 1):
                cur.execute("SELECT sum(sampletime * cps), sum(sampletime), " +
                            "ST_X(ST_Transform(ST_Centroid(ST_Collect(location)), 3663)), " +
                            "ST_Y(ST_Transform(ST_Centroid(ST_Collect(location)), 3663)) " +
                            "FROM histograms " +
                            "WHERE ST_Contains(ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 3663), 4326), location) " +
                            "AND time > %s AND time < %s",
                            (xx[i,j], yy[i,j], xx[i,j+1], yy[i+1,j], start, end))
                counts, time, x, y = cur.fetchone()
                if counts is None:
                    continue

                pts[i,j] = [x, y]
                C[i,j] = counts
                t[i,j] = time
        data.append((pts, C, t))

    vars = []
    for h in hs:
        hmin = h - 5
        hmax = h + 5
        N = 0
        s = 0
        n = 0

        for pts, C, t in data:
            for i in range(C.shape[0]):
                for j in range(C.shape[1]):
                    # SO MANY LOOPS
                    if t[i,j] == 0:
                        continue
                    for k in range(i, C.shape[0]):
                        for l in range(j, C.shape[1]):
                            if t[k,l] > 0 and hmin < dist(pts[i,j], pts[k,l]) < hmax:
                                tt = t[i,j] * t[k,l] / (t[i,j] + t[k,l])
                                N += tt
                                n += 1
                                s += tt * (C[i,j] / t[i,j] - C[k,l] / t[k,l])**2 - m
        if N != 0:
            vars.append([h, s / (2 * N), n])

    return np.array(vars)

# Some estimated variogram models for convenience
COV_ARL = make_exp_cov(72.1, 90.468, 2.0)
COV_STADIUM = make_exp_cov(723.98, 83.3789, 1.1458)
COV_CAMPUS = make_exp_cov(1347.61, 123.94, 1.5645)
