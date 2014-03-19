import matplotlib.pyplot as plt
import psycopg2
import numpy as np
import scipy as sp
from scipy.optimize import curve_fit
from datetime import datetime
from datetime import timedelta

conn = psycopg2.connect(database = "radiation", user = "radiation",
                        password = "radiation", host = "localhost")


def tempGain(start,end,mincount =0, maxcount = -1):
    """
    Plots the temperature gain and generates a best fit curve
    binmin and binmax are the minimum and maximum bins considered.
    Points outside [binmin,binmax] are ignored
    """
    #Fitting function
    def func(x,a,b):
        return a*np.power(x,1) + b*np.power(x,0)
    
    cur = conn.cursor()
    print 'Querying from database'
    if maxcount == -1:
        cur.execute("SELECT temp, cps FROM histograms WHERE time > %s "+
                    "AND time < %s AND cps > %s ORDER BY time ASC",
                    (start,end,mincount))
    else:
        cur.execute("SELECT temp, cps FROM histograms WHERE time > %s "+
                    "AND time < %s AND cps > %s AND cps < %s " +
                    "ORDER BY time ASC",
                    (start,end,mincount,maxcount))
    temps = []
    cps = []
    for row in cur:
        temps.append(row[0])
        cps.append(row[1])
    if len(cps) == 0:
        print 'No Data'
        return
    print 'Fitting Curve'
    popt, pcov = curve_fit(func, temps, cps)
    cps2 = []
    temps2 = range(15,45)
    print 'Creating curve'
    for temp in temps2:
        cps2.append(func(temp,popt[0],popt[1]))
    
    plt.plot(temps,cps, 'bo', temps2,cps2,'r')
    plt.xlabel("Temperature (Celsius)")
    plt.ylabel("Counts Per Second")
    plt.title("Temperature Gain")
    print 'Equation: '+repr(popt[0])+'x + '+repr(popt[1])
    plt.show()

def tempShift(start,end,binmin=0,binmax=4095):
    """
    Plots the temperature shift and generates a best fit curve
    binmin and binmax are the minimum and maximum bins considered.
    Points outside [binmin,binmax] are ignored
    """
    #Fitting Funciton
    def func(x,a,b,c):
        return a*np.power(x,2) + b*np.power(x,1) + c*np.power(x,0)
    
    cur = conn.cursor()
    print 'Querying from database'
    cur.execute("SELECT temp, histogram FROM histograms WHERE time > %s "+
                "AND time < %s ORDER BY time ASC", (start, end))
    temps = []
    peaks = []
    print 'Analyzing Data'
    for row in cur:
        peak = -1
        loc = -1
        i=0
        for elem in row[1]:
            if elem > peak:
                peak = elem
                loc = i
            i+=1
        if loc >binmin and loc <binmax:        
            peaks.append(loc)
            temps.append(row[0])

    if len(peaks) == 0:
        print 'No Data'
        return
    
    print 'Fitting Curve'
    popt, pcov = curve_fit(func, temps, peaks)
    peakopt = []
    temps2 = range(15,45)
    print 'Creating curve'
    for temp in temps2:
        peakopt.append(func(temp,popt[0],popt[1],popt[2]))

    print 'Plotting Data'
    plt.plot(temps,peaks,'bo', temps2,peakopt,'r')
    plt.xlabel("Temperature (Celsius)")
    plt.ylabel("Peak bin location")
    plt.title("Temperature Shift")
    print 'Equation: '+repr(popt[0])+'x^2 + '+repr(popt[1])+'x + '+repr(popt[2])
    plt.show()

#tempShift(datetime(2013,7,10),datetime(2013,7,20),binmin = 400)
#tempGain(datetime(2013,7,10),datetime(2013,7,20), mincount = 300,maxcount = 500)
