import psycopg2
import numpy as np
from datetime import datetime
from mpl_toolkits.basemap import Basemap
from UTC import utc

m = Basemap(projection="merc")
shp = m.readshapefile('maps/bus/bus', 'buses', drawbounds=False)

# Database
conn = psycopg2.connect(database = "radiation", user = "radiation", 
                        password = "radiation", host = "localhost")
cur = conn.cursor()

# Region of interest
topleft = (-97.74676, 30.28205)
bottomright = (-97.73434, 30.26377)
simulatedRunStart = datetime(2012, 7, 26, 13, 0, 0, 0, utc)

for shapedict, shape in zip(m.buses_info, m.buses):
    for point in shape:
        lat, lon = m(point[0], point[1], inverse=True)
        if lat > topleft[0] and lat < bottomright[0] \
           and lon > bottomright[1] and lon < topleft[1]:
            cur.execute("INSERT INTO histograms (time, location, sampletime, " +
                        "temp, cps, hdop, histogram, simulated) " +
                        "VALUES (%s, ST_GeomFromText('POINT(%s %s)', 4326), 10, " +
                                "25, 0, 1, %s, TRUE)",
                    (simulatedRunStart, lat, lon, list(np.zeros(4096))))

conn.commit()
cur.close()
conn.close()
