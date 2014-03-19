import psycopg2
import numpy as np
import analyze, nscrad
from scipy import io
from datetime import datetime
from util.UTC import utc

bins = nscrad.EQUAL_BINS
nbins = len(bins)
obsTime = 30 # aggregate 30 seconds of observations at a time

conn = psycopg2.connect(database = "radiation", user = "radiation",
                        password = "radiation", host = "localhost")

cur = conn.cursor()

startDate = datetime(2012, 9, 30, 10, 0, 0, 0, utc)
endDate = datetime(2012, 10, 5, 0, 0, 0, 0, utc)

print "Querying database"
cur.execute("SELECT sampletime, histogram FROM histograms " +
            "WHERE simulated = FALSE AND time > %s AND time < %s " +
            "ORDER BY time DESC",
            (startDate, endDate))

print "Reading old histograms"
oldHists = []
oldHist = np.zeros(len(bins))
hist = np.zeros(len(bins))
time = 0
for row in cur:
    d = nscrad.downsampleHistogram(row[1], bins)
    hist = np.add(hist, d)
    time += row[0]
    
    if time > obsTime:
        time = 0
        oldHists.append(hist)
        oldHist = np.add(oldHist, hist)
        hist = np.zeros(len(bins))

T = nscrad.getShapeMatrix(oldHist)

print "Making SCRs"
scrs = np.vstack(map(lambda h: np.dot(T, h), oldHists))

print "Computing SCR correlation"
scr_corr = np.corrcoef(scrs, rowvar=0)

print "Computing bin correlation"
bin_corr = np.corrcoef(np.vstack(oldHists), rowvar=0)

print "Saving data"
io.savemat("correlation.mat", {"scr": scr_corr, "bin": bin_corr}, oned_as="row")
