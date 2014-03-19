from RepeatedTimer import RepeatedTimer
from time import sleep

class StatusLED(RepeatedTimer):
    def __init__(self,pin,*args,**kwargs):
        self.portDict = {18 : 10 }        # maps pin -> GPIOport
        self.status = 'normal'
        self.intervalDict = {'normal' : 1, 'error' : .2, 'on' : 1, 'off' : 1}
        interval = self.intervalDict[self.status]
        self.port = self.portDict[pin]
        self.value = 0
        self.setupPort()
        RepeatedTimer.__init__(self,interval,self.blink,*args,**kwargs)
        self.start()

    def setStatus(self,status):
        try:
            self.interval = self.intervalDict[status]
            self.status = status
        except KeyError:
            print("Status {} not defined".format(status))

    def setupPort(self):
        # select port
        try:
            with open("/sys/class/gpio/export","w") as export:
                export.write("{}".format(self.port))
        except (IOError, OSError):
            with open("/sys/class/gpio/unexport","w") as unexport:
                unexport.write("{}".format(self.port))
            with open("/sys/class/gpio/export","w") as export:
                export.write("{}".format(self.port))
        # set to output
        with open("/sys/class/gpio/gpio{}/direction".format(self.port),"w") as direction:
            direction.write("{}".format("out"))

    def blink(self):
        if self.status == 'on':
            self.value = 1
        elif self.status == 'off':
            self.value = 0
        else:                             # toggle
            if self.value == 0:
                self.value = 1
            elif self.value == 1:
                self.value = 0
        # change value
        with open("/sys/class/gpio/gpio{}/value".format(self.port),"w") as value:
            value.write("{}".format(self.value))
        
# rt = StatusLED(18)
# try:
#     sleep(5) # your long-running job goes here...
#     rt.setStatus('on')
#     sleep(5)
#     rt.setStatus('error')
#     sleep(5)
# finally:
#     rt.stop() # better in a try/finally block to make sure the program ends!
