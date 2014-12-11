from __future__ import absolute_import
import serial, threading, time, pytz, os
from numpy import mean, sqrt, square
from datetime import datetime, timedelta
from pytz import timezone
from dateutil import parser
from gps import *

class GPSD(threading.Thread):

    def __init__(self, TZ, adjustTime):
        threading.Thread.__init__(self)
        self.daemon = True
        self.session = gps(mode=WATCH_ENABLE|WATCH_NEWSTYLE)
        self.running = True
        self.tz = timezone(TZ)
        self.tzOffset = (self.tz.localize(datetime(2014,1,1,0,0)) - pytz.utc.localize(datetime(2014,1,1,0,0)))
        self.tzOffsetHours = timedelta(hours=int(self.tzOffset.total_seconds() // 3600 % 24))
        print self.tzOffsetHours
        self.adjustTime = adjustTime in ['true', '1', 'True']
        self.previousGPSTime = None
        
    def run(self):
        while self.running:
          self.session.next()
          time.sleep(0.2)

    def stop(self):
        self.running = False
        self.session.close()
        self.join(2)

    def retry(self):
        self.session = gps(mode=WATCH_ENABLE|WATCH_NEWSTYLE)

    def getLocation(self):
        location = self.session.fix
        if type(location.time) == float:
          location.timestamp = self.tz.localize(datetime.fromtimestamp(location.time))
          if self.previousGPSTime == None or abs(location.timestamp - self.previousGPSTime) > timedelta(seconds=30):
            location.timestamp = location.timestamp - self.tzOffsetHours # some timezone is accounted for by GPS
        else:
          location.timestamp = parser.parse(location.time).astimezone(self.tz)
        location.gpsError = -1
        if location.mode == 2:
          location.gpsError = sqrt(mean(square([location.epx, location.epy])))
        if location.mode == 3:
          location.gpsError = sqrt(mean(square([location.epx, location.epy, location.epv])))
        location.time_accurate = False
        if(self.adjustTime and self.previousGPSTime is not None and location.gpsError >= 0):
          currentTime = datetime.now(self.tz)
          if abs(currentTime - location.timestamp).total_seconds() > 10:
            print "Updating System time from GPS to: " + str(location.timestamp)
            command = 'date --set="' + str(location.timestamp) + '"'
            os.system(command)
          location.time_accurate = True
        self.previousGPSTime = location.timestamp
        return location


class GPS(threading.Thread):
    """Use PySerial to read NMEA data off the chosen serial port."""

    def __init__(self, port):
        threading.Thread.__init__(self)
        self.currentLocation = None
        self.currentVelocity = None
        self.port = port
        self.running = threading.Event()
    
    def run(self):
        try:
            self.ser = serial.Serial(port=self.port, baudrate=4800, timeout=2)
        except serial.SerialException:
            print "Failed to connect to GPS on port %s" % self.port
            return
        while True:
            if not self.running.is_set():
                return
            line = self.ser.readline()
            if line.startswith(b'$GPGGA'):
                self.currentLocation = line
            elif line.startswith(b'$GPRMC'):
                self.currentVelocity = line
    
    def getLocation(self):
        """Return a (latitude, longitude, altitude, precision) tuple, or None
        if there is no fix. Altitude is in meters."""
        
        if self.currentLocation is None:
            return None # no GPS attached
        loc = self.currentLocation.strip().split(b',')
        if (loc[6] == b'0'):
            return None # no GPS fix
        
        # Latitude
        min = loc[2][2:]
        deg = loc[2][0:2]
        latitude = int(deg) + float(min) * (1.0/60)
        
        if loc[3] == b'S':
            latitude = -1 * latitude
        
        # Longitude
        min = loc[4][3:]
        deg = loc[4][0:3]
        longitude = int(deg) + float(min) * (1.0/60) 
        
        if loc[5] == b'W':
            longitude = -1 * longitude
        
        return (latitude, longitude, float(loc[9]), float(loc[8]))
    
    def getVelocity(self):
        """Return current velocity in miles per hour, or None."""
        if self.currentVelocity is None:
            return None
        try:
            velocity = self.currentVelocity.strip().split(b',')[7]
        except IndexError:
            return None
        if velocity == '':
            return None
        # GPS reports in knots, so we must convert to mph
        return float(velocity) * 1.151
    
if __name__ == '__main__':
#    gps = GPS('/dev/ttyUSB0')
#    gps.running.set()
#    gps.start()
    gpsd = GPSD("US/Central","true")
    try:
      gpsd.start()

      if sys.argv[1] == "time":
        timeout = 5
        location = gpsd.getLocation()
        while (location.time_accurate != True) and (timeout > 0):
          time.sleep(1)
          print timeout
          location = gpsd.getLocation()
          timeout = timeout - 1
        gpsd.stop()
        exit(0)
    
      while 1:
        time.sleep(5)
        location = gpsd.getLocation()
        attrs = vars(location)
        print "\n".join("%s: %s" % item for item in attrs.items())
        
    except (KeyboardInterrupt, SystemExit):
      gpsd.stop()
