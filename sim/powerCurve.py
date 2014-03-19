import csv, nscrad, analyze
import numpy as np
from scipy import stats
import matplotlib.pyplot as plt

bins = nscrad.EQUAL_BINS
ALPHA = 0.001

def loadSample(filename, bins, rate = None):
    """Load a sample histogram and downsample it to given bins. Optionally,
       scale to a specified rate of gammas."""
    bgr = csv.reader(open(filename, 'rb'))
    
    hist = nscrad.downsampleHistogram(map(int, bgr.next()), bins)
    if rate is not None:
        return hist * rate / np.sum(hist)
    
    return hist

def sampleSpectrum(hist):
    """Produce a sample histogram based on the given histogram,
       with added Poisson variability."""
    
    return np.array(map(np.random.poisson, hist))

def plotPowerCurve(startTime, endTime, bgRate = 50.0, sampleRate = 5.0,
                  sample="co60", background="arl-background", trials = 500):
    fig = plt.figure()
    timeRange = np.linspace(startTime, endTime)
    background = loadSample('samples/' + background + '.csv', bins, rate=bgRate)
    sample = loadSample('samples/' + sample + '.csv', bins, rate=sampleRate)
    T = nscrad.getShapeMatrix(loadSample('samples/reinhart-desk.csv', bins))
    
    powers = []
    for t in timeRange:
        # Generate background covariance matrix.
        bgs = []
        for i in range(5000):
            bgs.append(np.dot(T, sampleSpectrum(background * t)))
        
        invBgCov = np.dual.inv(np.cov(np.vstack(bgs), rowvar = 0))
        
        detections = 0
        for i in range(trials):
            spectrum = np.add(sampleSpectrum(background * t), sampleSpectrum(sample * t))
            p = stats.chi2.sf(nscrad.nscrad(spectrum, T, invBgCov)[1], len(bins) - 2)
            if p < ALPHA:
                detections += 1

        powers.append(float(detections) / float(trials))
    plt.plot(list(timeRange), powers)
    plt.title("Power curve")
    plt.xlabel("Observation time (s)")
    plt.ylabel("Probability of detection")
    plt.show()
