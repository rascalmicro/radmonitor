"""
Produce a plot of detector temperature over time.
"""
import matplotlib.pyplot as plt
import psycopg2
import numpy as np
from datetime import datetime

conn = psycopg2.connect(database = "radiation", user = "radiation", 
                        password = "radiation", host = "localhost")

def plotTemps(runStart, runEnd):
    """Produce a plot of detector temperatures over time.
    
    runStart, runEnd: datetime objects defining the interval to plot over
    """
    cur = conn.cursor()
    cur.execute("SELECT time,temp FROM histograms WHERE time > %s AND time < %s " +
                "ORDER BY time ASC",
                (runStart, runEnd))

    time = []
    temps = []
    for row in cur:
        time.append(row[0])
        temps.append(row[1])
    
    plt.plot(time,temps,'r.')
    plt.xlabel("Time")
    plt.ylabel("Temperature (Celsius)")
    plt.title("Sensor temperature")
    plt.gcf().autofmt_xdate()
    plt.show()
