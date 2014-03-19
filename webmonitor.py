#Runs the server for the web interface
#Look at monitor.js and monitor.html in web for the javascript/html code
#TODO: This code can probably be consolidated. Too many cur.execute calls

import cherrypy, psycopg2, json, calendar, os.path
#import util.battery as battery
from util.UTC import utc
from datetime import datetime, timedelta
from dateutil import parser
from cherrypy.lib.static import serve_file
from collections import deque
import getEnergy
import numpy as np
import socket
import sys

## Connect to database
HOST = "localhost"
conn = psycopg2.connect(database = "radiation", user = "radiation", 
                        password = "radiation", host = HOST)

config = {'/': {"tools.staticdir.root": os.path.abspath("web")},
          "/web/js": {"tools.staticdir.on": True,
                      "tools.staticdir.dir": "js"}
         }

class RecentLoc(object):
    def index(self, start, end):
        cur = conn.cursor()

        cur.execute("SELECT ST_X(ST_Transform(location,4326)), ST_Y(ST_Transform(location,4326)), cps " +
                    "from histograms WHERE simulated = false AND hdop >0 AND time > %s AND time < %s " +
                    "ORDER BY time DESC", parseTime(start,end))
        coords = [] #Longitude, Latitude
        cps = []
        for row in cur:
            coords.append([row[0],row[1]])
            cps.append(row[2])
        
        coords.reverse()
        return json.dumps({"coords": coords, "cps": cps})
    
    index.exposed = True

class RecentCPS(object):
    def index(self,start, end):
        cur = conn.cursor()
        cur.execute("SELECT cps, time FROM histograms " +
                    "WHERE time > %s AND time < %s AND simulated = false ORDER BY time DESC", 
                    parseTime(start,end))
        pts = []
        
        
        for row in cur:
            pts.append([calendar.timegm(row[1].utctimetuple()) * 1000, int(row[0])])
        
        return json.dumps({"cps": pts})
    
    index.exposed = True

class RecentHDOP(object):
    def index(self, start, end):
        cur = conn.cursor()
        cur.execute("SELECT hdop, time FROM histograms " +
                    "WHERE time > %s AND time <%s AND simulated = false ORDER BY time DESC",
                    parseTime(start,end))
        
        pts = []
        
        for row in cur:
            pts.append([calendar.timegm(row[1].utctimetuple()) * 1000, float(row[0])])
        
        return json.dumps({"hdop": pts})
        
    index.exposed = True

class RecentHist(object):
    def index(self, start, end):
        def calibrate(x):
            SLOPE = (1332.5 - 661.7) / (1049 - 534)
            INTERCEPT = -33.8
            return x*SLOPE + INTERCEPT
##        cur = conn.cursor()
##        cur.execute("SELECT temp, histogram FROM histograms " +
##                    "WHERE time > %s AND time < %s AND simulated = false", 
##                    parseTime(start,end))
##        histdata = np.zeros(5000)
##        step = 1
##        energyScale = range(0,step*5000,step)
##        for row in cur:
##            temp = row[0]
##            histogram = row[1]
##            energy = map(getEnergy.tempGain,temp*np.ones(4096), range(4096))
##            for i in range(len(energy)):
##                index = np.floor(energy[i]/step)
##                if index >=0 and index < len(histdata):
##                    histdata[index] = histdata[index]+histogram[i]
##        pts = []
##        for i in range(len(histdata)):
##            pts.append([energyScale[i],histdata[i]])
        
        cur = conn.cursor()
        cur.execute("SELECT histogram FROM histograms " +
                    "WHERE time > %s AND time < %s AND simulated = false", 
                    parseTime(start,end))
        hist = deque(np.zeros((0,4096)))

        pts = []

        for row in cur:
            hist.append(row[0])
        if len(hist) != 0:
            histdata = reduce(np.add,hist)
            i=0
            for elem in histdata:
                pts.append([calibrate(i),np.asscalar(np.float64(elem))])
                i += 1
        
        return json.dumps({"hist": pts})
    
    index.exposed = True

class Status(object):
    def index(self):
        cur = conn.cursor()
        cur.execute("SELECT cps, time, hdop, temp FROM histograms WHERE simulated = false " +
                    "ORDER BY time DESC LIMIT 1")
        row = cur.fetchone()
        return json.dumps({"cps": int(row[0]), "time": row[1].isoformat(),
                           # "battery": battery.batteryPercent(),
                           "battery": 0,
                           "hdop": row[2], "temp": round(row[3], 1)})
    
    index.exposed = True

def parseTime(start,end):
    try:
        start = parser.parse(start)
        end = parser.parse(end)
        return (start, end)
    except ValueError:
        cherrypy.log("Value Error: Not A Valid DateTime")

class Index(object):
    #Allows monitor.js to access the methods
    recentloc = RecentLoc()
    recentcps = RecentCPS()
    status = Status()
    recenthdop = RecentHDOP()
    recenthist = RecentHist()
    
    def index(self):
        return serve_file(os.path.abspath("web/monitor.html"), "text/html")

    index.exposed = True


print "Point your browser to:"
print "http://{0:s}:8080".format(socket.gethostbyname(socket.gethostname()))
print

#cherrypy.log.screen = False
cherrypy.config.update({'server.socket_host': '0.0.0.0'})
cherrypy.quickstart(Index(), config=config)

