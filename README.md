# Spectral anomaly mapping system #

## Requirements ##
 * Matplotlib v. 1.1.1
 * Matplotlib Basemap toolkit v. 1.0.5
 * Numpy 1.6
 * SciPy 0.11
 * PostgreSQL 8.4 (9+ preferred)
 * PostGIS 1.5+
 * Python 2.7
 * psycopg 2.4
 * eMorpho module

## Reference systems ##

Observations are stored in WGS 84 lat/lon coordinates (SRID 4326). Maps and
analysis are done on the NSRS 2007 Texas Central plane (SRID 3663), which
conveniently has coordinates in meters. This is a Lambert conformal conic
projection, so maps are always in that projection.

## Installation ##

### Set up Postgres ###

Note that the scripts expect a user named `radiation` with the password
`radiation`.

### Create user ###

    sudo -u postgres createuser radiation

### Create database `radiation` ###

    sudo -u postgres createdb -O radiation radiation

### Change password to `radiation` ###

    sudo -u postgres psql

    psql (9.1.8)
    Type "help" for help.

    postgres=# \password radiation
    Enter new password:
    Enter it again:
    postgres=# \q

### Log in as user "radiation" ###

    psql --host=localhost --user=radiation -W

### Install PostGIS ###

    cd /usr/share/postgresql/9.1/contrib/postgis-1.5
    sudo -u postgres createlang plpgsql radiation
    sudo -u postgres psql -f postgis.sql -d radiation
    sudo -u postgres psql -f spatial_ref_sys.sql -d radiation
    sudo -u postgres psql -f postgis_comments.sql -d radiation

### Import data ###

Postgres can import backup files from the command line console using the \i
command. Obtain a recent histograms.backup file and type these commands in the
directory containing it:

    psql --user=radiation --host=localhost -W
    radiation=> \i histograms.backup

*** Install eMorpho code
The emorpho_cpython module is on GitHub:
https://github.com/capnrefsmmat/emorpho-cpython

There is a linux branch in Git which contains the Linux version of the eMorpho
API. To install:

- install libftdi-dev and libusb-dev packages
- cd to emorpho_cpython directory
- python setup.py build
- sudo python setup.py install

** Tour
Each Python module should be reasonably well-documented with docstrings. Check
them for details.

- util/ contains a number of useful modules, such as the UTC and CST
  timezone specifications, the =gps= module, and the =battery= monitor module.
- web/ holds the static resources for the web monitor module.

There are a number of root-level modules:
- =headlessMonitor= records data without a Qt interface, using Linux-specific
  code to access =gpsd='s location interface. Records until killed.

** Collecting data
To record data, follow these steps:

- Plug in the GPS and scintillator via USB. The data collector script will not
  load without the scintillator plugged in, though it's fine without the GPS.
- Fire up =monitor.py= using the "Data collection" desktop shortcut. This will
  create a command line window and the graphical data collection interface;
  serious errors will appear in the command line window.
- The scintillator should be detected automatically; you will see a
  notification in the status bar saying the eMorpho has been detected and is
  warming up.
- You will need to specify the serial port which the GPS is plugged into. On
  the laptop this is usually COM8 or COM9; if you pick the wrong port, a
  "Failed to connect to GPS" message will appear in the command line window.
- Once everything is connected, you can check the "Collect data" box to start
  acquiring data from the scintillator. The last 30 samples will be aggregated
  and shown in the histogram display, and the most recent count rates will be
  graphed. The histogram display is uncalibrated.
- Check the "Record data" box to have the acquired data saved into Postgres.
- Check the "Power save" box to disable the updating of the graphs, which might
  save some CPU power. Probably not very much. Use is optional.
- Click the "Save spectrum" button if you want to record the currently
  displayed spectrum as a CSV file. You can also clear the displayed spectrum
  and start fresh.

If the laptop speakers are unmuted, the script will emit beeps if cables become
unplugged and data is not collected. If the GPS fix is lost, the script will
beep but data will still be collected, with the GPS HDOP recorded as -1 to note
that the position was unknown. (The sound code is Windows-specific and would
have to be removed on a Linux or Mac setup.)
