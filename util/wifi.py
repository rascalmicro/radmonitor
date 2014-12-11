import subprocess, threading, os, time

class WiFi(threading.Thread):

  def __init__(self):
    threading.Thread.__init__(self)
    self.Up = False
    os.system("echo heartbeat > /sys/class/leds/beaglebone\:green\:usr3/trigger")
    self.running = True
    self.timeoutDefault = 1
    self.timeout = self.timeoutDefault

  def run(self):
    while self.running:
      try:
        subprocess.check_call(["iwconfig 2>&1 | grep ESSID | grep -q 'AtheyRadMap'"], shell = True)
      except subprocess.CalledProcessError:
        if self.Up != False:
          self.Up = False
          os.system("echo heartbeat > /sys/class/leds/beaglebone\:green\:usr3/trigger")
        os.system("ifdown wlan0")
        os.system("ifup wlan0")
        self.timeout = self.timeout - 1
        if self.timeout < 0:
          self.timeout = self.timeoutDefault
          self.stop()
          time.sleep(3)
      else:
        if self.Up != True:
          self.Up = True
          os.system("echo default-on > /sys/class/leds/beaglebone\:green\:usr3/trigger")
        time.sleep(5)

  def stop(self):
    print "In stop"
    if self.running == True:
      self.running = False
      print "Taking down interface"
      os.system("ifdown wlan0")
      self.Up = False
    os.system("echo none > /sys/class/leds/beaglebone\:green\:usr3/trigger")
