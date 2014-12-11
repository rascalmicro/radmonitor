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
from numpy import isnan, mean, sqrt, square
from util.wifi import WiFi as wifi
from util.gpsd import GPSD as gps
import os, signal, sys, json, datetime
from geopy import distance

SAMPLE_TIME = 2 # seconds
wifi = wifi()
TZ = ""
sensor = "0"
version = "0.0"
gpsBase = (0.0, 0.0)
gpsRange = 100

def loadConfig():
  json_config = open('/home/debian/radmonitor-master/radmonitor.config')
  config = json.load(json_config)
  json_config.close()
  for setting in config["radsettings"]:
    setattr(e, setting, config["radsettings"][setting])
  SAMPLE_TIME = config["sampleTime"]
  e.clearStats()
  e.startTimedHistogram(SAMPLE_TIME)
  return config

def haltMonitor(signal, frame):
  wifi.stop()
  gps.stop()
  print "Exiting headlessMonitor cleanly"
  sys.exit(0)

signal.signal(signal.SIGINT, haltMonitor)

def connectToRad():
  e.scan()
  while e.open(0) == False:
    print "Could not connect to Rad Sensor"
    os.system("echo heartbeat > /sys/class/leds/beaglebone\:green\:usr2/trigger")
    time.sleep(5)
    e.scan()
  os.system("echo none > /sys/class/leds/beaglebone\:green\:usr2/trigger")

conn = psycopg2.connect(database = 'radiation', user = 'radiation',
                        password = 'radiation', host = 'localhost')

cur = conn.cursor()

wifi.start()

e = emorpho.eMorpho()
connectToRad()

config = loadConfig()

gpsBase = (config["baseCoords"]["latitude"], config["baseCoords"]["longitude"])
gpsRange = config["baseCoords"]["range"]
sensor = config["sensor"]
version = config["version"]
TZ = config["timezone"]
AdjustTime = config["gpsTime"]

gps = gps(TZ, AdjustTime)
gps.start()

# def getFix(session):
#    """Use gpsd session to get a TPV report. Return None if no fix is currently
#       available. Return gpsd's dict otherwise."""

#    for report in session:
#        if report["class"] == "TPV":
#            if report["mode"] == 3:
#                return report
#            else:
#                return None

state = gpsState = True
gpsTimeout = 0
sessionCounter = 0

while True:
    time.sleep(SAMPLE_TIME)
    sessionCounter = sessionCounter + 1
    if sessionCounter > 1000:
      loadConfig()
      sessionCounter = 0
#    location = gps.getFix()
    location = gps.getLocation()
    if location.longitude == 0.0 or isnan(location.longitude):
        print "Error: No GPS location"
        gpsTimeout = gpsTimeout + 1
        if gpsState:
          os.system("echo default-on > /sys/class/leds/beaglebone\:green\:usr2/trigger")
          gpsState = False
        else:
          os.system("echo none > /sys/class/leds/beaglebone\:green\:usr2/trigger")
          gpsState = True 
        if gpsTimeout >= 5:
          print "Restarting GPS"
          gpsTimeout = 0
          gps.retry()
        continue
    else:
       baseDistance = distance.vincenty(gpsBase, (location.latitude, location.longitude)).meters 
       if baseDistance <= gpsRange:
         if wifi.running == False:
           print "In range of router"
           wifi.start()

    hist = e.readHistogram()
    if hist == False:
        print "Error: Couldn't read the histogram"
        connectToRad()
        continue

    stats = e.readStats()
    e.startTimedHistogram(SAMPLE_TIME)

    # TODO: There's some logic in monitor.py to handle GPS dropouts by
    # recording HDOP of -1. We should replicate that here.a
    cur.execute("INSERT INTO histograms (location, hdop, time, sampletime, temp, cps, histogram, altitude, sensor, version) " +
                "VALUES (ST_GeomFromText('POINT(%s %s)', 4326), %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (location.longitude, location.latitude, location.gpsError, location.timestamp, SAMPLE_TIME,
                 e.getTemperature(), 
                 stats["cps"], 
                 hist, 
                 location.altitude, 
                 sensor, 
                 version))
    conn.commit()

    print "Added Entry ", location.timestamp, stats["cps"], location.latitude, location.longitude, location.gpsError, distance.vincenty(gpsBase, (location.latitude, location.longitude)).meters
    if state:
      os.system("echo default-on > /sys/class/leds/beaglebone\:green\:usr1/trigger")
      state = False
    else:
      os.system("echo none > /sys/class/leds/beaglebone\:green\:usr1/trigger")
      state = True
