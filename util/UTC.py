#TODO: To be deprecated. Use dateutil.tz.tzutc() instead
from datetime import timedelta, tzinfo

# A UTC class for consistent timekeeping.
ZERO = timedelta(0)
HOUR = timedelta(hours=1)
class UTC(tzinfo):
    """UTC"""

    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO

utc = UTC()
