"""Find the smallest source detectable at a given distance using SCRAM.

Here we have a selected region of roadway (the northwest corner of PRC)
specified in `run`. A simulated source, with spectrum taken from the `samples`
directory, is injected at varying distances from the roadway using locations
given in `source`. The source size is increased until, after `trials` repeat
trials, the fraction of observations with SCR above `detectionThreshold` is
greater than `power`. Results are printed as distance,size pairs, with the
distance in meters and the size in milliCuries.
"""

import csv, psycopg2, math, radmap.nscrad as nscrad
import numpy as np
from datetime import datetime
import scipy.io as io
import scipy as sp
from scipy import linalg
from radmap.util.UTC import utc
from radmap.util.simTools import sizeToCPS, sampleSpectrum

bins = nscrad.EQUAL_BINS

source = {"sample": "2013-cs137-5cm", "start": (-97.7305876668583, 30.3912440498782),
          "toward": (-97.7347124201772, 30.3926811858099)}

spectr = csv.reader(open('samples/' + source["sample"] + ".csv", "rb"))
sourceSpectrum = nscrad.downsampleHistogram(np.array(map(int, spectr.next())), bins)

# normalize to make a probability distribution
sourceSpectrum /= float(np.sum(sourceSpectrum))

run = {"bl": (-97.7316888053854, 30.3890105120164),
       "tr": (-97.7298107514453, 30.393032984632),
       "start": datetime(2012, 8, 6, 15, 0, 0, 0, utc),
       "end": datetime(2012, 8, 6, 20, 0, 0, 0, utc)}

initialSize = 1 # milliCuries
dists = 40 # number of different distances to test
detectionThreshold = 114 # 83 for 1% false positive. 114 for spatial
power = 0.8
trials = 50

# Database
conn = psycopg2.connect(database = "radiation", user = "radiation",
                        password = "radiation", host = "localhost")
cur = conn.cursor()

xx = np.linspace(source["start"][0], source["toward"][0], dists)
yy = np.linspace(source["start"][1], source["toward"][1], dists)

# Read historical samples for baseline
cur.execute("SELECT histogram FROM histograms " +
            "WHERE ST_Contains(ST_MakeEnvelope(%s, %s, %s, %s, 4326), location) " +
            "AND time < %s ORDER BY time DESC LIMIT 500",
            (run["bl"][0], run["bl"][1], run["tr"][0], run["tr"][1], run["start"]))

oldHist = nscrad.sumHistograms(map(lambda h: nscrad.downsampleHistogram(h[0], bins),
                                   cur))
oldTime = cur.rowcount * 2

# Read the base run samples
cur.execute("SELECT sum(sampletime) " +
            "FROM histograms WHERE time > %s AND time < %s " +
            "AND ST_Contains(ST_MakeEnvelope(%s, %s, %s, %s, 4326), location)",
            (run["start"], run["end"], run["bl"][0], run["bl"][1], run["tr"][0],
             run["tr"][1]))

sampleTime = cur.fetchone()[0]

T = nscrad.getShapeMatrix(oldHist)

for i in range(dists):
    cur.execute("SELECT ST_Distance(ST_Transform(location, 3663), " +
                "ST_Transform(ST_SetSRID(ST_Point(%s, %s), 4326), 3663)) as dist " +
                "FROM histograms " +
                "WHERE ST_Contains(ST_MakeEnvelope(%s, %s, %s, %s, 4326), location) " +
                "AND time > %s AND time < %s " +
                "ORDER BY dist ASC LIMIT 1",
                (xx[i], yy[i], run["bl"][0], run["bl"][1], run["tr"][0], run["tr"][1],
                 run["start"], run["end"]))
    minDist = cur.fetchone()[0]

    cur.execute("SELECT ST_Distance(ST_Transform(location, 3663), " +
                "ST_Transform(ST_SetSRID(ST_Point(%s, %s), 4326), 3663)), " +
                "histogram FROM histograms " +
                "WHERE ST_Contains(ST_MakeEnvelope(%s, %s, %s, %s, 4326), location) " +
                "AND time > %s AND time < %s",
                (xx[i], yy[i], run["bl"][0], run["bl"][1], run["tr"][0],
                 run["tr"][1], run["start"], run["end"]))

    # cleanHist will be a list of (hist, dist) tuples
    cleanHist = map(lambda h: (nscrad.downsampleHistogram(h[1], bins), h[0]), cur)

    for size in np.arange(initialSize, 1400, 1):
        # Because of random variation, repeat multiple times and average S
        ss = []
        for i in range(trials):
            hist = np.zeros(len(bins))

            for point in cleanHist:
                dist = point[1]
                s = np.add(point[0],
                           sampleSpectrum(sourceSpectrum * sizeToCPS(size, dist)))
                hist = np.add(hist, s)

            # Now, analyze.
            # take old histogram & new histogram and run SCR
            cov = nscrad.makeCovMat(oldHist, hist, oldTime, sampleTime,
                                    overDisperse=nscrad.DISPERSION)

            scrs, S = nscrad.nscrad(hist, T, linalg.inv(cov))
            ss.append(S)

        ss = np.array(ss)
        if float(len(ss[ss > detectionThreshold])) / len(ss) > power:
            print "%f,%f" % (minDist, size)
            initialSize = size
            break
