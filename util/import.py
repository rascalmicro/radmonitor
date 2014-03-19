import psycopg2, csv
from datetime import datetime

conn = psycopg2.connect(database = "radiation", user = "radiation", 
                        password = "radiation", host = "localhost")
cur = conn.cursor()

reader = csv.reader(open('netl-test-run.csv', 'rb'))

for row in reader:
    timestamp = datetime.strptime(row[3], "%Y-%m-%dT%H:%M:%S.%f")
    print row[0:6]
    try:
        cur.execute("INSERT INTO histograms (location, hdop, time, sampletime, temp, cps, histogram) " + 
                    "VALUES (ST_GeomFromText('POINT(%s %s)',4326), %s, %s, %s, %s, %s, %s)",
                    (float(row[1]), float(row[0]), float(row[2]), timestamp, float(row[4]),
                     float(row[5]), float(row[6]), map(float, row[7:4103])))
    except ValueError:
        pass


conn.commit()
cur.close()
conn.close()
