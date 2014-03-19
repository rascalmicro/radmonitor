"""
Make maps using stored radiation data and the Matplotlib basemap toolkit.
"""

import psycopg2, nscrad, krige
import numpy as np
import scipy as sp
from datetime import datetime, timedelta
from matplotlib.colors import LogNorm, LinearSegmentedColormap

import matplotlib.pyplot as plt
from mpl_toolkits.basemap import Basemap

conn = psycopg2.connect(database = "radiation", user = "radiation", 
                        password = "radiation", host = "localhost")

def cps_plot(start, end, shapefile = "arl", resolution = 100, max_hdop = 50, lessScary=False):
    """Produce a hexbin plot of mean count rates.
    
    Uses the Lambert azimuthal equal-area projection.
    
    start, end: datetime objects (with timezone) specifying interval to plot
    shapefile: ESRI shapefile to use as background, in `maps/` directory
    resolution: how many spatial bins should we divide the region into?
    max_hdop: If points have HDOP greater than this, omit them
    lessScary: if True, switch to color scale that compares to an X-ray
    """
    global conn
    cur = conn.cursor()

    center, width, height = get_center_and_size(start, end, max_hdop, cur)

    fig = plt.figure()
    m = Basemap(projection="laea", lon_0=center[0], lat_0=center[1],
                width=width * 1.2, height=height * 1.2)
    shp = m.readshapefile('maps/' + shapefile + '/' + shapefile, 'roads',
                          linewidth=1)

    cur.execute("SELECT ST_X(ST_Transform(location, 4326)), ST_Y(ST_Transform(location, 4326)), " +
                "cps FROM histograms WHERE time > %s AND time < %s AND hdop < %s AND hdop > 0",
                (start, end, max_hdop))
    
    xx = []
    yy = []
    C = []
    for row in cur:
        if row[2] == 0:
            continue
        x, y = m(row[0], row[1])
        xx.append(x)
        yy.append(y)
        C.append(row[2])

    if lessScary:
        C = np.clip(np.array(C), 0, 200)
        cdict = {"red":   [(0.0, 0.0, 1.0),
                           (0.85, 0.2, 1.0),
                           (1.0, 0.7, 0.7)],
                 "green": [(0.0, 0.0, 1.0),
                           (0.85, 0.2, 0.5),
                           (1.0, 0.0, 0.0)],
                 "blue":  [(0.0, 0.0, 1.0),
                           (0.85, 0.2, 0.5),
                           (1.0, 1.0, 0.0)]}
        cm = LinearSegmentedColormap("lessScary", cdict)
    else:
        cm = "gist_heat_r"

    bins = m.hexbin(np.array(xx), np.array(yy), C=C, reduce_C_function=np.mean,
                    gridsize=resolution, cmap=cm, vmax=250)
    if lessScary:
        cb = m.colorbar(bins, ticks=[50, 75, 100, 125, 150, 175, 200, 250])
        cb.ax.set_yticklabels(["50", "75", "100", "125", "150", "175", "200", "> 30,000\n chest x-ray"])
    else:
        cb = m.colorbar(bins)
    cb.set_label("cps")
    
    plt.title("Counts per second")
    plt.show()

def get_aggregated_observations(cur, xx, yy, start, end, max_hdop, bins=[(0, 4095)]):
    n = (xx.shape[0] - 1) * (xx.shape[1] - 1)
    pts = np.zeros((n, 2))
    C = np.zeros((n, len(bins)))
    t = np.zeros((n, 1))

    n = 0
    for i in range(xx.shape[0] - 1):
        for j in range(xx.shape[1] - 1):
            cur.execute("SELECT sum(sampletime), " +
                        "ST_X(ST_Transform(ST_Centroid(ST_Collect(location)), 3663)), " +
                        "ST_Y(ST_Transform(ST_Centroid(ST_Collect(location)), 3663)) " +
                        "FROM histograms " +
                        "WHERE ST_Contains(ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 3663), 4326), location) " +
                        "AND time > %s AND time < %s AND hdop < %s",
                        (xx[i,j], yy[i,j], xx[i,j+1], yy[i+1,j], start, end, max_hdop))
            time, x, y = cur.fetchone()
            if time is None:
                continue

            cur.execute("SELECT histogram FROM histograms " +
                        "WHERE ST_Contains(ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 3663), 4326), location) " +
                        "AND time > %s AND time < %s AND hdop < %s",
                        (xx[i,j], yy[i,j], xx[i,j+1], yy[i+1,j], start, end, max_hdop))
            hist = nscrad.downsampleHistogram(nscrad.sumHistograms(cur), bins)

            pts[n] = [x, y]
            C[n] = hist
            t[n,0] = time
            n += 1
    return pts[0:n], C[0:n,:], t[0:n]

def cps_contour(start, end, cov_func, shapefile = "arl", spacing = 20,
                max_hdop = 50, plotVars=False):
    """Produce a contour map of count rates in an area, using kriging."""
    global conn
    cur = conn.cursor()

    center, width, height = get_center_and_size(start, end, max_hdop, cur)

    fig = plt.figure()
    m = Basemap(projection="laea", lon_0=center[0], lat_0=center[1],
                width=width * 1.2, height=height * 1.2)
    shp = m.readshapefile('maps/' + shapefile + '/' + shapefile, 'roads',
                          linewidth=1)

    xx, yy = nscrad.make_grid(cur, start, end, spacing, 3663)

    pts, C, t = get_aggregated_observations(cur, xx, yy, start, end, max_hdop)

    pred_pts = np.transpose(np.vstack([xx.ravel(), yy.ravel()]))

    preds, vars = krige.krige_at(pts, t, C, pred_pts,
                                 cov_func)

    # Convert coordinates back to WGS 84 lat/lon and allow Basemap to handle
    # conversion to map coordinates.
    xx, yy = convert_to_wgs84(xx, yy, cur)

    if plotVars:
        col = m.contourf(xx, yy, np.reshape(np.sqrt(vars), xx.shape), latlon=True)
        cb = m.colorbar(col)
        cb.set_label("std. dev. cps")
        plt.title("Count rate prediction error")
    else:
        col = m.contourf(xx, yy, np.reshape(preds, xx.shape), latlon=True,
                         cmap=plt.cm.get_cmap('gist_heat_r'))
        cb = m.colorbar(col)
        cb.set_label("cps")
        plt.title("Counts per second")
    plt.show()

def anomaly_contour(bgInterval, newInterval, cov_func, bins=nscrad.EQUAL_BINS,
                    shapefile = "arl", alpha=0.05, spacing = 20, max_hdop = 50):
    global conn
    cur = conn.cursor()

    center, width, height = get_center_and_size(start, end, max_hdop, cur)

    fig = plt.figure()
    m = Basemap(projection="laea", lon_0=center[0], lat_0=center[1],
                width=width * 1.2, height=height * 1.2)
    shp = m.readshapefile('maps/' + shapefile + '/' + shapefile, 'roads',
                          linewidth=1)

    xx, yy = nscrad.make_grid(cur, newInterval[0], newInterval[1], spacing, 3663)

    oldPts, oldC, oldT = get_aggregated_observations(cur, xx, yy, bgInterval[0],
                                                     bgInterval[1], max_hdop, bins)
    pts, C, t = get_aggregated_observations(cur, xx, yy, newInterval[0],
                                            newInterval[1], max_hdop, bins)

    nx = int(np.ceil(np.abs(np.max(pts[:,0] - np.min(pts[:,0]))) / spacing))
    ny = int(np.ceil(np.abs(np.max(pts[:,1] - np.min(pts[:,1]))) / spacing))

    bgPreds, bgVars = krige.krige_at(oldPts, oldT, oldC, pts, cov_func)

    ps = krige.anomaly_detect(bgPreds, bgVars, C, np.tile(t, C.shape[1]))
    pmax = krige.determine_p_threshold(ps, alpha)

    # Transform back to WGS84 and then to map coordinates
    for i in range(pts.shape[0]):
        cur.execute("SELECT ST_X(ST_Transform(ST_PointFromText('POINT(%s %s)', 3663), 4326)), " +
                    "ST_Y(ST_Transform(ST_PointFromText('POINT(%s %s)', 3663), 4326))",
                    (pts[i, 0], pts[i, 1], pts[i, 0], pts[i, 1]))
        p = cur.fetchone()
        pts[i] = m(p[0], p[1])

    col = m.hexbin(pts[:,0], pts[:,1], C=ps, cmap=plt.cm.get_cmap("gist_heat"),
                   vmin=0.0, vmax=pmax, gridsize=(nx, ny))

    cb = m.colorbar(col)
    cb.set_label("p value")
    plt.title("Count rate anomalies")
    plt.show()

def obs_time_plot(start, end, shapefile = "arl", resolution = 100):
    """Produce a hexbin plot of mean observation times.
    
    Uses the Lambert azimuthal equal-area projection.
    
    start, end: datetime objects (with timezone) specifying interval to plot
    shapefile: ESRI shapefile to use as background, in `maps/` directory
    resolution: how many spatial bins should we divide the region into?
    """
    global conn
    cur = conn.cursor()

    center, width, height = get_center_and_size(start, end, 50, cur)
    
    fig = plt.figure()
    m = Basemap(projection="laea", lon_0=center[0], lat_0=center[1],
                width=width * 1.2, height=height * 1.2)
    shp = m.readshapefile('maps/' + shapefile + '/' + shapefile, 'roads',
                          linewidth=1)
    
    cur.execute("SELECT ST_X(ST_Transform(location, 4326)), ST_Y(ST_Transform(location, 4326)), " +
                "sampletime " +
                "FROM histograms WHERE time > %s AND time < %s",
                (start, end))
    
    xx = []
    yy = []
    C = []
    for row in cur:
        x, y = m(row[0], row[1])
        xx.append(x)
        yy.append(y)
        C.append(row[2])
    
    bins = m.hexbin(np.array(xx), np.array(yy), C=C, reduce_C_function=np.sum,
                    gridsize=resolution, cmap='gist_heat_r')
    cb = m.colorbar(bins)
    cb.set_label("seconds")
    
    plt.title("Observation time")
    plt.show()

def scr_plot(start, end, shapefile = "arl", binsize = 250, pvalues = False,
             max_hdop = 50):
    """Produce an SCR anomaly map of a region.
    
    Uses the Lambert conformal projection, centered on Central Texas.
    (SRID 3663)
    
    start, end: datetime objects (with timezone) specifying interval to plot
    shapefile: ESRI shapefile to use as background, in `maps/` directory
    binsize: side length of each square spatial bin, in meters
    pvalues: boolean. If True, plot as p-values (log scale) rather than D^2
    max_hdop: If points have HDOP greater than this, omit them
    """
    global conn
    cur = conn.cursor()
    
    center, width, height = get_center_and_size(start, end, max_hdop, cur)
    
    fig = plt.figure()
    # This sets up the NSRS 2007 Texas Central projection, SRID 3663 -- mostly.
    # False easting and northing are not included, and center point is centroid
    # of our data, not the NSRS center point.
    m = Basemap(projection="lcc", lat_1=31.88333333333333, lat_2=30.11666666666667,
                lat_0=center[1], lon_0=center[0],
                rsphere=(6378137.00, 6356752.3142),
                width=width * 1.2, height=height * 1.2)
    
    shp = m.readshapefile('maps/' + shapefile + '/' + shapefile, 'roads',
                          linewidth=1)
    
    xx, yy = nscrad.make_grid(cur, start, end, binsize, 3663)

    bins = nscrad.EQUAL_BINS
    
    scrs = np.zeros((xx.shape[0] - 1, xx.shape[1] - 1))
    
    for i in range(xx.shape[0] - 1):
        for j in range(xx.shape[1] - 1):
            cur.execute("SELECT sum(sampletime) FROM histograms " +
                        "WHERE ST_Contains(ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 3663), 4326), location) " +
                        "AND time > %s AND time < %s",
                        (xx[i,j], yy[i,j], xx[i,j+1], yy[i+1,j], start, end))
            sampleTime = cur.fetchone()[0]
            
            p, S, _, _ = nscrad.SCRRegion(cur, [xx[i,j], xx[i,j+1]],
                                          [yy[i,j], yy[i+1,j]], [start, end],
                                          sampleTime, bins,
                                          overDisperse=nscrad.DISPERSION)

            if S is None:
                scrs[i, j] = -1.0
                continue
            
            if pvalues:
                scrs[i, j] = p
            else:
                scrs[i, j] = S
    
    # Convert coordinates back to WGS 84 lat/lon and allow Basemap to handle
    # conversion to map coordinates.
    xx, yy = convert_to_wgs84(xx, yy, cur)
    
    # If there are simulated points with 0 cps, these are sources
    cur.execute("SELECT ST_X(location), ST_Y(location) FROM histograms " +
                "WHERE simulated = TRUE AND cps = 0 " +
                "AND time > %s AND time < %s",
                (start, end))

    for source in cur:
        pt = m(source[0], source[1])
        m.plot(pt[0], pt[1], 'ko')
    
    if pvalues:
        scrs[scrs == 0.0] = 1e-20
    scrs = np.ma.masked_values(scrs, -1.0)
    if pvalues:
        colors = m.pcolormesh(xx, yy, scrs, latlon=True, antialiased=True,
                              cmap="gist_heat", norm=LogNorm(vmin=10**(-50), vmax=1.0))
        c = m.colorbar(colors)
        c.set_label("p value")
    else:
        colors = m.pcolormesh(xx, yy, scrs, vmin=1.0, vmax=200.0, latlon=True, antialiased=True, cmap='gist_heat_r')
        c = m.colorbar(colors)
        c.set_label("$D^2$")
    
    plt.title("SCRs")
    plt.show()

def convert_to_wgs84(xx, yy, cur):
    """Use PostGIS to convert meshgrids back to WGS84 for Matplotlib to use."""
    for i in range(xx.shape[0]):
        for j in range(xx.shape[1]):
            cur.execute("SELECT ST_X(ST_Transform(ST_PointFromText('POINT(%s %s)', 3663), 4326)), " +
                        "ST_Y(ST_Transform(ST_PointFromText('POINT(%s %s)', 3663), 4326))",
                        (xx[i, j], yy[i, j], xx[i, j], yy[i, j]))
            xx[i, j], yy[i, j] = cur.fetchone()
    return xx, yy

def get_center_and_size(start, end, max_hdop, cur):
    cur.execute("SELECT ST_X(ST_Centroid(ST_Extent(location))), " +
                "ST_Y(ST_Centroid(ST_Extent(location))) " +
                "FROM histograms WHERE time > %s AND time < %s AND hdop < %s AND hdop > 0",
                (start, end, max_hdop))
    center = cur.fetchone()

    cur.execute("SELECT ST_XMax(ST_Extent(ST_Transform(location, 3663))) - " +
                "ST_XMin(ST_Extent(ST_Transform(location, 3663))), " +
                "ST_YMax(ST_Extent(ST_Transform(location, 3663))) - " +
                "ST_YMin(ST_Extent(ST_Transform(location, 3663)))" +
                "FROM histograms " +
                "WHERE time > %s AND time < %s AND hdop < %s AND hdop > 0",
                (start, end, max_hdop))
    width, height = cur.fetchone()

    return center, width, height
