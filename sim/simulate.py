"""Create a batch of simulated data with injected sources.

Takes the `baseRun` (all data recorded in a specified time interval) and
replicates it on new `runDates` with additional injected sources. These sources
are pulled from spectra in the `samples/` directory and placed at specified
locations. If `location` is None, the source is assumed to be everywhere, so
you must specify the count rate `cps`. Otherwise, specify the source's size
in milliCuries. This will be converted to a count rate using the conversion
factor in `util.simTools.sizeToCPS`.

An entire list of `runDates` can be specified. Each new run will be unique,
as the injected spectra and observed data are subject to Poisson random
variation using `util.simTools.sampleSpectrum`.

All simulated data is injected into the database with the `simulated` column
set to TRUE, so it may be easily removed or ignored if necessary.
"""

import csv, math, psycopg2
import numpy as np
from datetime import datetime
from scipy import stats
from radmap.util.CST import cst
from radmap.util.simTools import sizeToCPS, sampleSpectrum

# NETL source
#sources = [{"sample": "cs137", "location": (-97.7249026082566, 30.3897750645203),
#            "basecps": 100000.0, "basedist": 1.0}]
# Downtown
sources = [{"sample": "arl-background", "location": None, "cps": 50},
           {"sample": "brick", "location": (-97.74036, 30.27469), "size": 30000},
           {"sample": "paleo", "location": (-97.74234, 30.26765), "size": 1000},
           {"sample": "2013-cs137-5cm", "location": (-97.74036, 30.27469),
            "size": 3500}]

baseRun = (datetime(2013, 7, 26, 0, 0, 0, 0, cst), datetime(2013, 7, 27, 6, 0, 0, 0, cst))

runDates = [datetime(2013, 8, 27, 12, 0, 0, 0, cst),
            datetime(2013, 8, 27, 13, 0, 0, 0, cst),
            datetime(2013, 8, 27, 14, 0, 0, 0, cst),
            datetime(2013, 8, 27, 15, 0, 0, 0, cst),
            datetime(2013, 8, 27, 16, 0, 0, 0, cst),
            datetime(2013, 8, 27, 17, 0, 0, 0, cst),
            datetime(2013, 8, 28, 12, 0, 0, 0, cst),
            datetime(2013, 8, 28, 13, 0, 0, 0, cst),
            datetime(2013, 8, 28, 14, 0, 0, 0, cst),
            datetime(2013, 8, 28, 15, 0, 0, 0, cst),
            datetime(2013, 8, 28, 16, 0, 0, 0, cst),
            datetime(2013, 8, 28, 17, 0, 0, 0, cst)]

# Database
conn = psycopg2.connect(database = "radiation", user = "radiation", 
                        password = "radiation", host = "localhost")
cur = conn.cursor()

# Read spectral data from set of samples
samples = dict()
for source in sources:
    if source["location"] is not None:
        # Insert a sample with no counts at the location of the source
        cur.execute("INSERT INTO histograms (time, location, sampletime, " +
                    "temp, cps, hdop, histogram, simulated) " +
                    "VALUES (%s, ST_GeomFromText('POINT(%s %s)', 4326), 1, " +
                            "25, 0, 1, %s, TRUE)",
                    (runDates[0], source["location"][0],
                     source["location"][1], list(np.zeros(4096))))

    if source["sample"] not in samples:
        spectr = csv.reader(open('samples/' + source["sample"] + ".csv", "rb"))
        spectrum = np.array(map(int, spectr.next()))
        total = float(np.sum(spectrum))
        
        # normalize to make a probability distribution
        samples[source["sample"]] = spectrum / total

# Read the base run samples
cur.execute("SELECT id, ST_X(location), ST_Y(location), time, " +
            "histogram, sampletime, temp, cps, hdop " +
            "FROM histograms WHERE time > %s AND time < %s",
            (baseRun[0], baseRun[1]))

points = cur.fetchall()

print "Samples to simulate: %d" % cur.rowcount
print "Sample runs: %d" % len(runDates)
print "Total points: %d" % (len(runDates) * cur.rowcount,)
i = 1
for simulatedRunStart in runDates:
    print "Run %d" % i
    i += 1
    for sample in points:
        id = sample[0]
        hist = sample[4]
        sampleTime = sample[5]
        
        newHist = sampleSpectrum(hist)
        newTime = (sample[3] - baseRun[0]) + simulatedRunStart
        for source in sources:
            if source["location"] is not None:
                cur.execute("SELECT ST_Distance(ST_Transform(location, 3663), " +
                            "ST_Transform(ST_GeomFromText('POINT(%s %s)', 4326), 3663)) " +
                            "FROM histograms WHERE id = %s",
                            (source["location"][0], source["location"][1], id))
                dist = cur.fetchone()[0]
                numCounts = sizeToCPS(source["size"], dist)
            else:
                numCounts = source["cps"] * sampleTime
            
            newHist = np.add(sampleSpectrum(samples[source["sample"]] * numCounts), newHist)
            
        cur.execute("INSERT INTO histograms (time, location, sampletime, temp, cps, hdop, histogram, simulated) " +
                    "VALUES (%s, ST_GeomFromText('POINT(%s %s)', 4326), %s, %s, %s, %s, %s, TRUE)",
                    (newTime, sample[1], sample[2], sampleTime, sample[6], np.sum(newHist) / sampleTime, sample[8],
                     list(newHist)))
    conn.commit()

cur.close()
conn.close()
