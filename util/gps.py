import serial, threading, time, emorpho

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
    gps = GPS('/dev/ttyUSB1')
    gps.running.set()
    gps.start()
    
    while 1:
        time.sleep(5)
        print(gps.currentLocation)
