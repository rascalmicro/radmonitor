"""Tools for simulating radioactive sources."""

import numpy as np
import math

def sizeToCPS(mCi, dist):
    """Convert a source size in miliCuries to an approximate number of counts
       at dist (meters), using calibrations with Cs-137 sources of known sizes.
    """

    knownSize = 0.000844 # mCi
    knownDist = 0.05 # m
    knownCounts = 630 # cps
    mu = 0.0100029 # attenuation coefficient, in units of m^{-1}, for 660 keV in air

    return (mCi / knownSize) * knownCounts * math.pow(knownDist / dist, 2) * \
            math.exp(-mu * (knownDist + dist))

def sampleSpectrum(hist):
    """Produce a sample histogram based on the given histogram,
       with added Poisson variability."""

    # Enforce minimum value in histogram, since stats.poisson.rvs doesn't like
    # distributions with mean zero. This adds a bit of noise, with bins with 0
    # counts in the source spectrum occasionally getting one or two counts in
    # the simulation.
    return np.array(map(np.random.poisson, np.clip(hist, 0.0001, float("+inf"))))
