"""Command-line monitoring interface for Linux.

Uses gpsd to acquire GPS data. gpsd has good documentation, so be sure to
check that. Watch out, though -- if you use gpsd to interact with a GPS unit
and gpsd speaks its proprietary binary protocol, it will have the unit switch
to use that, and when you plug it back in to a Windows machine you will not be
able to read location data. You need to set it back to NMEA first using the
gpsd tools.

Here we simply record new data every SAMPLE_TIME seconds until killed. If GPS
lock is lost, the data is simply dropped.
"""

import emorpho, time, psycopg2
import gps
from datetime import datetime
import dateutil.parser
from statusLED import StatusLED

led = StatusLED(18)
led.setStatus('on')

SAMPLE_TIME = 2 # seconds

conn = psycopg2.connect(database = 'radiation', user = 'radiation',
                        password = 'radiation', host = 'localhost')

cur = conn.cursor()

session = gps.gps(mode=gps.WATCH_ENABLE|gps.WATCH_NEWSTYLE)

e = emorpho.eMorpho()
e.scan()
e.open(0)

# Set up with values provided by Bridgeport. This should stay in sync with
# monitor.py
e.HV = 1025
e.fineGain = 43500
e.gain = 10100
e.compression = 7
e.holdOff = 1500
e.pulseThreshold = 10
e.pileUp = 0
e.clearStats()
e.startTimedHistogram(SAMPLE_TIME)

def getFix(session):
    """Use gpsd session to get a TPV report. Return None if no fix is currently
       available. Return gpsd's dict otherwise."""

    for report in session:
        if report["class"] == "TPV":
            if report["mode"] == 3:
                return report
            else:
                return None

while True:
    time.sleep(SAMPLE_TIME)
    location = getFix(session)
    if location is None:
        led.setStatus('error')
        print "Error: No GPS location"
        continue
    else:
        led.setStatus('on')

    hist = e.readHistogram()
    if hist == False:
        led.setStatus('error')
        print "Error: Couldn't read the histogram"
        continue
    else:
        led.setStatus('on')

    stats = e.readStats()
    e.startTimedHistogram(SAMPLE_TIME)

    # TODO: There's some logic in monitor.py to handle GPS dropouts by
    # recording HDOP of -1. We should replicate that here.
    if location:
        cur.execute("INSERT INTO histograms (location, hdop, time, sampletime, temp, cps, histogram, altitude) " +
                "VALUES (ST_GeomFromText('POINT(%s %s)', 4326), %s, %s, %s, %s, %s, %s, %s)",
                (location["lon"], location["lat"], location["mode"], dateutil.parser.parse(location.time), SAMPLE_TIME,
                 e.getTemperature(), stats["cps"], hist, location["alt"]))
    else:
        cur.execute("INSERT INTO histograms (location, hdop, time, sampletime, temp, cps, histogram, altitude) " +
                    "VALUES (ST_GeomFromText('POINT(0 0)', 4326), %s, %s, %s, %s, %s, %s, %s)",
                (location["lon"], location["lat"], -1, dateutil.parser.parse(location.time), SAMPLE_TIME,
                 e.getTemperature(), stats["cps"], hist, location["alt"]))
    # cur.execute("INSERT INTO histograms (location, hdop, time, sampletime, temp, cps, histogram, altitude) " +
    #             "VALUES (ST_GeomFromText('POINT(%s %s)', 4326), %s, %s, %s, %s, %s, %s, %s)",
    #             (location["lon"], location["lat"], -1, datetime.fromtimestamp(location.time), SAMPLE_TIME,
    #              e.getTemperature(), stats["cps"], hist, location["alt"]))
    conn.commit()

e.close()
conn.close()
