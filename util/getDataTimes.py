#Script to aggomerate observation times

from datetime import datetime, timedelta
import psycopg2

##CHANGE THESE TWO AS NECESSARY
HOST = "localhost"              #Host of the database
INTERVAL = timedelta(0,0,0,0,1) #Time interval beyond which a new entry is made

conn = psycopg2.connect(database = "radiation", user = "radiation",
                        password = "radiation", host = HOST)
cur = conn.cursor()
cur.execute("SELECT time FROM histograms WHERE simulated = false order by time ASC")

times = []  #Holds the start and end times as tuples
start = None

for row in cur:
    current = row[0]
    if start == None:
        start = current

    #If the difference between between the last 2 times is greater than the interval 
    elif current - last > INTERVAL:
        times.append((start,last))
        start = current

    last = current

times.append((start,last))

for row in times:
    print "Start: " + row[0].__str__() + "|End: " + row[1].__str__()
