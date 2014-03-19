# Collect GPS-tagged histograms and show live graphs.

from pyqtgraph.Qt import QtGui, QtCore
from collections import deque

from ui.ui_monitorwindow import Ui_MonitorWindow
from util.gps import GPS
from datetime import datetime
from dateutil.tz import tzutc
from dateutil.tz import tzlocal
from eMorphoConfig import eMorphoSetup

import numpy as np
import pyqtgraph as pg
import emorpho
import psycopg2
import csv
import winsound
import util.battery as battery

## Configuration
NUM_HIST_SAMPLES = 30       # Number of samples to include in histogram display
NUM_COUNT_SAMPLES = 30      # Number of samples to include in cps display
SAMPLE_TIME = 2             # Time to spend collecting each histogram, in seconds
HOST = "localhost"          # Host of the database. Change this to connect to right host

## Connect to database
conn = psycopg2.connect(database = "radiation", user = "radiation", 
                        password = "radiation", host = HOST)

## Connect to eMorpho
e = emorpho.eMorpho()
serial_nums = e.scan()
print "Serial Numbers: " + repr(serial_nums)
e.open(0)

# Calibration settings provided by Bridgeport for CsI(Na) detector
# TODO: Abstract out to allow for multiple detectors
eMorphoSetup(e,serial_nums[0])
e.clearStats()
e.startTimedHistogram(1)  # This clears out the histogram buffer with a new set of data

class MonitorWindow(QtGui.QMainWindow):
    def __init__(self, e, conn):
        QtGui.QMainWindow.__init__(self)

        # Set up the user interface from Designer.
        self.ui = Ui_MonitorWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("Radiation sensor")
        
        # Status bar!
        self.mph = QtGui.QLabel()
        self.ui.statusbar.addPermanentWidget(self.mph)
        self.cps = QtGui.QLabel()
        self.ui.statusbar.addPermanentWidget(self.cps)
        self.HV = QtGui.QLabel()
        self.ui.statusbar.addPermanentWidget(self.HV)
        self.temp = QtGui.QLabel()
        self.ui.statusbar.addPermanentWidget(self.temp)
        self.gpsStatus = QtGui.QLabel()
        self.ui.statusbar.addPermanentWidget(self.gpsStatus)
        self.ui.statusbar.showMessage("eMorpho warming up.", 5000)
        
        # Database
        self.conn = conn
        self.cur = self.conn.cursor()

        #EMorpho
        self.e = e
        self.updateMorphoStatus()
        self.serial_no = serial_nums[0]

        #GPS
        self.GPS = GPS('COM1')

        #Histogram
        self.histPlot = self.ui.histogram.getPlotItem()
        self.histPlot.setTitle("Histogram")
        self.histPlot.setLabel("bottom", "Bin")
        self.histPlot.setLabel("left", "Counts")
        self.histogram = self.histPlot.plot(np.zeros(4096), pen=(255,0,0))
        self.histograms = deque(np.zeros((0, 4096)), NUM_HIST_SAMPLES)

        #CPS (Counts per Second)
        self.countPlot = self.ui.counts.getPlotItem()
        self.countPlot.setTitle("Counts per second")
        self.countPlot.setLabel("bottom", "Time", units="s")
        self.countPlot.setLabel("left", "Counts per second")
        self.countPlot.showGrid(y = True, x = False)
        self.counts = self.countPlot.plot([], pen=(0,255,0))

        #Battery
        self.batteryCheck = QtCore.QTimer()
        self.batteryCheck.timeout.connect(self.checkBattery)
        self.batteryCheck.setInterval(30000)

        #Update timer
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update)
        self.setSampleTime(SAMPLE_TIME)
        self.ui.sampleTime.setValue(SAMPLE_TIME)

        #Binding signals to functions
        QtCore.QObject.connect(self.ui.sampleTime, 
                               QtCore.SIGNAL('valueChanged(double)'),
                               self.setSampleTime)
        
        QtCore.QObject.connect(self.ui.collectData,
                               QtCore.SIGNAL('stateChanged(int)'),
                               self.setCollectData)
                               
        QtCore.QObject.connect(self.ui.gpsSerial,
                               QtCore.SIGNAL('currentIndexChanged(QString)'),
                               self.setGPSPort)

        QtCore.QObject.connect(self.ui.saveSpectrum,
                               QtCore.SIGNAL("clicked()"),
                               self.saveSpectrum)
        
        QtCore.QObject.connect(self.ui.clearSpectrum,
                               QtCore.SIGNAL("clicked()"),
                               self.clearSpectrum)

    def clearSpectrum(self):
        """Clears the spectrum"""
        self.histogram.setData(np.zeros(4096))
        self.histograms = deque(np.zeros((0, 4096)), NUM_HIST_SAMPLES)

    def saveSpectrum(self):
        """Saves Spectrum in CSV format"""
        spectrum = reduce(np.add, self.histograms)
        
        dialog = QtGui.QFileDialog()
        dialog.setFileMode(QtGui.QFileDialog.AnyFile)
        dialog.setNameFilter("CSV (*.csv)")
        
        if dialog.exec_():
            f = open(str(dialog.selectedFiles()[0]), 'ab')
            writer = csv.writer(f, delimiter = ',')
            writer.writerow(spectrum)
            f.close()
            self.ui.statusbar.showMessage("Spectrum saved to CSV.")
    
    def setCollectData(self, state):
        """Starts/Stops collection of data based on checkbox"""
        if state == 0:
            self.timer.stop()
            self.batteryCheck.stop()
            self.GPS.running.clear()
        if state == 2:
            self.timer.start()
            self.batteryCheck.start()
            self.e.startTimedHistogram(SAMPLE_TIME)
            self.GPS = GPS(str(self.ui.gpsSerial.currentText()))
            self.GPS.running.set()
            self.GPS.start()
    
    def setGPSPort(self, port):
        """Sets the GPS port"""
        self.GPS.running.clear()
        self.GPS = GPS(str(port))
        self.GPS.running.set()
        if self.ui.collectData.isChecked():
            self.GPS.start()
    
    def updateMorphoStatus(self):
        """Sets Text Area To Show EMorpho Information"""
        self.HV.setText("HV: {HV}".format(HV=str(round(e.HV))))
        
    def checkBattery(self):
        """Gives warning if battery is low"""
        if battery.onBattery() and battery.batteryPercent() < 15:
            self.ui.statusbar.showMessage("Warning: Low battery.", SAMPLE_TIME * 30000)
            winsound.Beep(880, 300)
            winsound.Beep(880, 300)
            winsound.Beep(880, 300)
    
    def update(self):
        """Updates the GUI"""
        hist = self.e.readHistogram()

        #No Emorpho
        if hist == False:
            winsound.Beep(880, 300)
            self.ui.statusbar.showMessage("Warning: eMorpho is not connected.", SAMPLE_TIME * 1000)
            print "eMorpho disconnected; can't record at %s" % datetime.now(tzlocal())
            return

        #Updating Data
        self.histograms.append(hist)
        cps = self.e.readStats()["cps"]
        location = self.GPS.getLocation()
        velocity = self.GPS.getVelocity()

        #Updates Database
        if self.ui.recordData.isChecked():

            #With GPS Reading
            if location is not None:
                self.cur.execute("INSERT INTO histograms (location, hdop, time, sampletime, temp, cps, histogram, altitude, serial_no) " + 
                                 "VALUES (ST_GeomFromText('POINT(%s %s)', 4326), %s, %s, %s, %s, %s, %s, %s, %s)",
                                 (location[1], location[0], location[3], datetime.now(tzutc()), SAMPLE_TIME,
                                  self.e.getTemperature(), cps, hist, location[2], self.serial_no))
                self.conn.commit()

            #Without GPS Reading
            else:
                self.cur.execute("INSERT INTO histograms (location, hdop, time, sampletime, temp, cps, histogram, altitude, serial_no) " + 
                                 "VALUES (ST_GeomFromText('POINT(0 0)', 4326), -1, %s, %s, %s, %s, %s, %s, %s)",
                                 (datetime.now(tzutc()), SAMPLE_TIME,
                                  self.e.getTemperature(), cps, hist, -1, self.serial_no))
                self.conn.commit()
                winsound.Beep(880, 300)
                self.ui.statusbar.showMessage("Warning: no GPS fix.", SAMPLE_TIME * 1000)
                print "No GPS at %s" % datetime.now(tzlocal())

        #Updating Text Areas
        self.cps.setText("cps: {cps}".format(cps=round(cps)))
        self.countData.append(cps)
        
        self.temp.setText(u"{temp} °C".format(temp=round(self.e.getTemperature(), 1)))

        #Clear and Restart EMorpho
        self.e.startTimedHistogram(SAMPLE_TIME)
        self.e.clearStats()
    
        # in power-save mode, avoid doing reduce() and plotting
        if not self.ui.powerSave.isChecked():
            histData = reduce(np.add, self.histograms)
            self.histogram.setData(histData)
            self.counts.setData(self.countTimes[-len(self.countData):], 
                                list(self.countData))

        #GPS Text
        if location is not None:
            self.gpsStatus.setText("{lat:0.2f}, {lon:0.2f}. {alt:0.1f} m. HDOP {dop:0.1f}".format(lat=location[0],
                                                                                    lon=location[1],
                                                                                    alt=location[2],
                                                                                    dop=location[3]))
        else:
            self.gpsStatus.setText("No fix")
            
        if velocity is not None:
            self.mph.setText("{mph:0.1f} mph".format(mph=velocity))
        else:
            self.mph.setText("? mph")
    
    def setSampleTime(self, time):
        """Sets Sample Time"""
        global SAMPLE_TIME
        SAMPLE_TIME = time
        self.timer.setInterval(1000 * SAMPLE_TIME)
        self.countData = deque([], NUM_COUNT_SAMPLES)
        self.countTimes = np.arange(-(NUM_COUNT_SAMPLES - 1) * SAMPLE_TIME, 
                                    SAMPLE_TIME, SAMPLE_TIME)
    
    def closeEvent(self, event):
        self.e.close()
        self.GPS.running.clear()
        self.cur.close()
        self.conn.close()

app = QtGui.QApplication([])
window = MonitorWindow(e, conn)

## Start Qt event loop unless running in interactive mode or using pyside.
import sys
if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
    window.show()
    app.exec_()
