# Analyze spectra stored in PostGIS for temporal anomalies.
#
# Uses the N-SCRAD algorithm to detect when spectra are inconsistent with
# previously-recorded spectra in the same region. Currently treats all past
# spectra equally -- has no idea that background may gradually change over
# time. Should implement a Kalman filter or some other method to predict
# background spectra.
#
# Alex Reinhart

#Note:  Make sure to run correlation.py before running this, or it will crash
#Note:  The times in the GUI are in local time. Make sure to convert appropriately
#TODO:  There are too many cur.executes floating around, and some are repeated. Probably need to restructure
#TODO:  Repainting issues when moving the ROI around in the map for newest versions of PyQT and pyqtgraph
#       May be due to dependencies. Investigate and fix. To hack around this, minimize window to force a repaint
#TODO:  Probably should only load data once, instead of reloading for every call to updateHistogram
#TODO:  Perhaps use server-side cursors if memory during loading is an issue
#TODO:  Probably should use threading/async/callbacks whenever using cur.execute
#TODO:  Add option to select data from individual detectors
#TODO:  Should abstract out the calibration function (and make it detector dependent)

from pyqtgraph.Qt import QtGui, QtCore
from ui.ui_analyzewindow import Ui_AnalyzeWindow
from datetime import datetime, timedelta
from dateutil.tz import tzlocal

import getEnergy
import numpy as np
import scipy as sp
import scipy.signal
import pyqtgraph as pg
import psycopg2
import nscrad
import math
import csv
import multiprocessing
import time
import cProfile
import pstats
import io

# Mahalanobis distances are roughly chi-squared distributed if the input
# variables are multinormal, with BINS - 1 degrees of freedom. We choose to
# alarm when p < ALPHA.
ALPHA = 10.0e-12

# Energy calibration. Derived from 1333 keV line of Co-60 and 661 keV line of Cs-137.
#SLOPE = (1332.5 - 661.7) / (978 - 493)
#INTERCEPT = -20.2
SLOPE = (1332.5 - 661.7) / (1049 - 534)
INTERCEPT = -33.8
HOST = "localhost"  # Host of the database. Change this to connect to right host

## Connect to database
conn = psycopg2.connect(database = "radiation", user = "radiation", 
                        password = "radiation", host = HOST)

def SCRCell(args):
    """Called by multiprocessing's Pool.map to run SCR in a grid square.
    Returns the SCR squares so that it can be drawn"""
    i, j, xx, yy, start, end, bins, stepsize = args

    # psycopg2 does not appreciate sharing connections between forked processes
    nconn = psycopg2.connect(database = "radiation", user = "radiation",
                             password = "radiation", host = HOST)
    cur = nconn.cursor()
    cur.execute("SELECT sum(sampletime) FROM histograms " +
                "WHERE ST_Contains(ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 3663), 4326), location) " + 
                "AND time > %s AND time < %s",
                (xx[i,j], yy[i,j], xx[i,j+1], yy[i+1,j], start, end))
    sampleTime = cur.fetchone()[0]
    
    _, S, _, _ = nscrad.SCRRegion(cur, [xx[i,j], xx[i,j+1]],
                                  [yy[i,j], yy[i+1,j]], [start, end],
                                  sampleTime, bins)
    if S is None:
        return None
    
    center = (xx[i,j] + (xx[i,j+1] - xx[i,j])/2, yy[i,j] + (yy[i+1,j] - yy[i,j])/2)
    return {"pos": center, "size": stepsize, "symbol": "s",
            "brush": (255, 50, 50, np.clip(4 * S, 0, 255))}


    
class AnalyzeWindow(QtGui.QMainWindow):
    def __init__(self, conn):
        QtGui.QMainWindow.__init__(self)
        
        self.pool = multiprocessing.Pool()
        
        self.conn = conn
        self.cur = conn.cursor()

        # Set up the user interface from Designer.
        self.ui = Ui_AnalyzeWindow()
        self.ui.setupUi(self)
        self.setWindowTitle("Radiation analysis")

        #Combo Box
        self.cur.execute("SELECT DISTINCT serial_no FROM HISTOGRAMS")
        for row in self.cur:
            self.ui.eSerial.addItem(row[0])

        #Binding signals to methods
        QtCore.QObject.connect(self.ui.plot, QtCore.SIGNAL("clicked()"), self.plot)
        QtCore.QObject.connect(self.ui.exportHistogram, QtCore.SIGNAL("clicked()"), self.export)
        QtCore.QObject.connect(self.ui.actionFind_Peaks, QtCore.SIGNAL("triggered()"), self.findPeaks)
        QtCore.QObject.connect(self.ui.eSerial, QtCore.SIGNAL("currentIndexChanged(QString)"),self.updateSerial)

        #Setting up the map
        self.map = pg.ScatterPlotItem(size=2, pen=pg.mkPen(None), brush=pg.mkBrush(255, 255, 255, 120))
        self.ui.map.setTitle("Map")
        self.ui.map.addItem(self.map)
        self.ui.map.setAspectLocked()
        self.ui.map.showGrid(False, False)
        #Setting up the ROI (Region of Interest)
        self.mapROI = pg.RectROI([10, 10], [1, 1], pen=(0,9))
        self.mapROI.sigRegionChangeFinished.connect(self.updateHistogram)
        self.mapROI.sigRegionChanged.connect(self.updateCoords)
        self.ui.map.addItem(self.mapROI)

        #Setting up the histogram
        self.histPlot = self.ui.histogram.getPlotItem()
        self.histPlot.setTitle("Histogram")
        self.histPlot.setLabel("bottom", "Energy (keV)")
        self.histPlot.setLabel("left", "Counts")
        self.histdata = np.zeros(4096)  #Histogram data array
        self.histogram = self.histPlot.plot(self.histdata, pen=(255,0,0))

        #Setting up the SCR plot
        self.scrPlot = self.ui.scrs.getPlotItem()
        self.scrPlot.setTitle("SCRs")
        self.scrPlot.setLabel("bottom", "Bin Number")
        self.scrPlot.setLabel("left", "SCR")
        self.scrs = self.scrPlot.plot(np.zeros(4096), pen=(255,255,255))
        
        # Vertical energy cursors for histogram/SCR view
        # Need two vertical lines because adding one to both plots crashes Python.
        self.vLine = pg.InfiniteLine(angle=90, movable=False)
        self.vLine2 = pg.InfiniteLine(angle=90, movable=False)
        self.histPlot.addItem(self.vLine, ignoreBounds=True)
        self.scrPlot.addItem(self.vLine2, ignoreBounds=True)
        self.histProxy = pg.SignalProxy(self.histPlot.scene().sigMouseMoved,
                                        rateLimit=60, slot=self.mouseMoved)
        self.scrProxy = pg.SignalProxy(self.scrPlot.scene().sigMouseMoved,
                                       rateLimit=60, slot=self.mouseMoved)

        #Set Time in the GUI
        self.ui.dataAfter.setDateTime(datetime.now(tzlocal()) - timedelta(1))
        self.ui.dataBefore.setDateTime(datetime.now(tzlocal()))
        
        self.bins = nscrad.EQUAL_BINS
    def plot(self):
        """Plot a map of the observed data points in the chosen time interval."""
        pr = cProfile.Profile()
        pr.enable()
        start = self.ui.dataAfter.dateTime().toPyDateTime()
        end = self.ui.dataBefore.dateTime().toPyDateTime()

        size = self.ui.binSize.value()

        #Draws the SCR grid on the map
        scrs = self.getSCRs(start, end, size)
        self.map.setData(scrs, pxMode=False)

        #Draws the points on the map
        self.cur.execute("SELECT ST_X(ST_Transform(location, 3663)), ST_Y(ST_Transform(location, 3663)), " +
                         "histogram FROM histograms WHERE time > %s AND time < %s AND hdop > 0",
                         (start, end))
        points = []
        for row in self.cur:
            points.append([row[0], row[1]])

        self.ui.map.clear()
        if len(points) > 0:
            self.map.setSize(3)
            self.map.addPoints(pos=points)
            self.ui.map.addItem(self.map)
            self.mapROI.setPos(np.subtract(np.mean(points, axis=0),[size/2,size/2]), update=False)
            self.mapROI.setSize([size, size]) #Note: Sends SigRegionChangedFinished Signal
            self.ui.map.addItem(self.mapROI)

        pr.disable()
        pr.print_stats()
    
    def getSCRs(self, start, end, binsize):
        """Returns the SCR squares to be plotted on the map"""
        xx, yy = nscrad.make_grid(self.cur, start, end, binsize, 3663)
        if xx is None or yy is None:
            return []

        
        cells = []
        for i in range(xx.shape[0] - 1):
            for j in range(xx.shape[1] - 1):
                cells.append((i, j, xx, yy, start, end, self.bins, binsize))

        points = self.pool.map(SCRCell,cells)
        return filter(lambda p: p is not None, points)
    
    def updateCoords(self, roi):
        """As the ROI moves, update the display of its size."""
        state = roi.getState()
        self.ui.regionWidth.setText("{0:0.2f} m".format(state["size"][0]))
        self.ui.regionHeight.setText("{0:0.2f} m".format(state["size"][1]))
        self.ui.regionDiag.setText("{0:0.2f} m".format(math.sqrt(state["size"][0]**2 + state["size"][1]**2)))
    
    def mouseMoved(self, evt):
        """For updating the vertical lines in histplot and scrPlot"""
        pos = evt[0]
        if self.histPlot.sceneBoundingRect().contains(pos) or \
           self.scrPlot.sceneBoundingRect().contains(pos):
            mousePoint = self.histPlot.vb.mapSceneToView(pos)
            energy = mousePoint.x()
            self.vLine.setPos(mousePoint.x())
            self.vLine2.setPos(mousePoint.x())
            self.ui.curEnergy.setText("{0:0.0f} keV".format(energy))
    
    def updateHistogram(self, roi):
        """Show a histogram of all the combined data in the selected region,
           along with N-SCRAD results and helpful statistics."""
        state = roi.getState()
        
        lowX = state["pos"][0]
        highX = state["pos"][0] + state["size"][0]
        
        lowY = state["pos"][1]
        highY = state["pos"][1] + state["size"][1]
        
        start = self.ui.dataAfter.dateTime().toPyDateTime()
        end = self.ui.dataBefore.dateTime().toPyDateTime()
        
        self.cur.execute("SELECT avg(cps), sum(sampleTime), count(id) FROM histograms " +
                         "WHERE ST_Contains(ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 3663), 4326), location) " + 
                         "AND time > %s AND time < %s AND hdop > 0",
                         (lowX, lowY, highX, highY, start, end))
        stats = self.cur.fetchone()

        #Updating Text Areas and Plots
        if stats[0] is not None:
            self.ui.cps.setText("{0:0.1f}".format(stats[0]))
            self.ui.obsTime.setText("{0:0.1f} s".format(stats[1]))
            self.ui.dataPoints.setText("{0:d}".format(stats[2]))
        else:
            self.ui.cps.setText("0")
            self.ui.obsTime.setText("0")
            self.ui.dataPoints.setText("0")

        p, S, scrs, histogram = nscrad.SCRRegion(self.cur, [lowX, highX],
                                                 [lowY, highY], [start, end],
                                                 stats[1], self.bins)

        print scrs
        
        #start of Rey's code for temp gain calibration
        reyconn = psycopg2.connect(database = "radiation", user = "radiation",
                            password = "radiation", host = "localhost")
        reycur = reyconn.cursor()
        reycur.execute("SELECT temp, histogram FROM histograms " +
                       "WHERE ST_Contains(ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 3663), 4326), location) " +
                       "AND time > %s AND time < %s AND hdop > 0",
                       (lowX, lowY, highX, highY, start, end))

        step = 1
        maxEnergy = 6000
        self.histdata = np.zeros(np.floor(maxEnergy/step))
        self.energyScale = range(0,maxEnergy,step)
        
        for row in reycur:
            temp = row[0]
            histogram = row[1]
            self.energy = map(getEnergy.tempGain,temp*np.ones(4096), range(4096))
            for i in range(len(self.energy)):
                index = np.floor(self.energy[i]/step)
                if index >=0:
                    self.histdata[index] = self.histdata[index]+histogram[i]
            
            
        
        self.histogram.setData(self.energyScale, self.histdata)
        self.ui.counts.setText("{0:0.0f}".format(sum(histogram)))
        self.plotSCRs(scrs)
        
        if p is None:
            self.ui.nscrad.setText("N/A")
            self.ui.pvalue.setText("N/A")
        else:
            if p < ALPHA:
                self.ui.nscrad.setText("{0:0.2f} (alarm)".format(S))
            else:
                self.ui.nscrad.setText("{0:0.2f}".format(S))
            self.ui.pvalue.setText("{0:0.4f}".format(p))

    #TODO: Add an input area in the GUI so that the widths parameter can be adjusted dynamically
    def findPeaks(self):
        """Calculates the peaks"""
        peakInd = sp.signal.find_peaks_cwt(self.histdata, np.arange(10,150))
        print "bin location: " + repr(peakInd)
        print "Counts: " + repr(np.array(self.histdata)[peakInd])

    #TODO: Finish this. Issues: Have to edit wayy to many execute statements, need to restructure code
    def updateSerial(self, serial):
        """Updates the serial number selected by user"""
        if serial == 'All':
            self.serial = '*'
        else:
            self.serial = serial

    def plotSCRs(self, scrs):
        """Plot the given SCRs to show per-bin deviations."""
        data = np.zeros(4096)
        i = 0
        for bin in self.bins[1:]:
            data[bin[0]:bin[1]] = -scrs[i]
            i += 1
        self.scrs.setData(range(0,4096), list(data))
    
    def export(self):
        """Export Histogram to csv"""
        state = self.mapROI.getState()
        
        lowX = state["pos"][0]
        highX = state["pos"][0] + state["size"][0]
        
        lowY = state["pos"][1]
        highY = state["pos"][1] + state["size"][1]
        
        start = self.ui.dataAfter.dateTime().toPyDateTime()
        end = self.ui.dataBefore.dateTime().toPyDateTime()
        self.cur.execute("SELECT histogram FROM histograms " +
                         "WHERE ST_Contains(ST_Transform(ST_MakeEnvelope(%s, %s, %s, %s, 3663), 4326), location) " + 
                         "AND time > %s AND time < %s",
                         (lowX, lowY, highX, highY, start, end))

        if self.cur.rowcount > 0:
            histogram = nscrad.sumHistograms(self.cur)
        else:
            histogram = np.zeros(4096)
        
        dialog = QtGui.QFileDialog()
        dialog.setFileMode(QtGui.QFileDialog.AnyFile)
        dialog.setNameFilter("CSV (*.csv)")
        
        if dialog.exec_():
            f = open(str(dialog.selectedFiles()[0]), 'ab')
            writer = csv.writer(f, delimiter = ',')
            writer.writerow(histogram)
            f.close()
            self.ui.statusbar.showMessage("Spectrum saved to CSV.")
    
    def closeEvent(self, event):
        self.cur.close()
        self.conn.close()
        self.pool.terminate()

if __name__ == "__main__":
    app = QtGui.QApplication([])
    window = AnalyzeWindow(conn)
    ## Start Qt event loop unless running in interactive mode or using pyside.
    import sys
    if (sys.flags.interactive != 1) or not hasattr(QtCore, 'PYQT_VERSION'):
        window.show()
        app.exec_()
