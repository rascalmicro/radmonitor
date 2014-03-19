def eMorphoSetup(e, serial):
    """Put eMorpho configurations here"""
    if serial == 'eRC0331':
        e.HV                = 1025
        e.fineGain          = 43500
        e.gain              = 10100
        e.compression       = 7
        e.holdOff           = 1500
        e.pulseThreshold    = 10
        e.pileUp            = 0
    elif serial == 'eRC1036':
        e.HV                = 580
        e.fineGain          = 33168
        e.gain              = 1100
        e.compression       = 3
        e.holdOff           = 78
        e.pulseThreshold    = 10
        e.pileUp            = 0
    else:
        print "Serial Number " + serial + " Was Not Found."
        raise ValueError()
