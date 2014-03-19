import psycopg2

def tempGain(temp,bin):
    if temp<32:
        SLOPE = 1.28
        INTERCEPT = -9.83
        ENERGY = SLOPE*bin + INTERCEPT
    #for 32<temp<38
    elif temp<38:
        SLOPE = 1.34
        INTERCEPT = -12.02
        ENERGY = SLOPE*bin + INTERCEPT
    #for 38<temp<40
    elif temp<40:
        SLOPE = 1.37
        INTERCEPT = -13.41
        ENERGY = SLOPE*bin + INTERCEPT
    #for 40<temp<42
    elif temp<42:
        SLOPE = 1.38
        INTERCEPT = -10.06
        ENERGY = SLOPE*bin + INTERCEPT
    else:
        SLOPE = 1.43
        INTERCEPT = -12.96
        ENERGY = SLOPE*bin + INTERCEPT
    #print "Slope is ", SLOPE, "and intercept is ", INTERCEPT
    return ENERGY
    #print "The slope is ", SLOPE,"and the intercept is ", INTERCEPT, "for a detector with a temp of ", temp

