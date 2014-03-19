#TODO: To be deprecated
from datetime import tzinfo, timedelta

# A Central time class.
HOUR = timedelta(hours=1)
class CST(tzinfo):
    """CST"""

    def utcoffset(self, dt):
        return -6 * HOUR

    def tzname(self, dt):
        return "CST"

    def dst(self, dt):
        return HOUR

cst = CST()
