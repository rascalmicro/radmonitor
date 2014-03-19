import ctypes
from ctypes import wintypes

class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ('ACLineStatus', wintypes.BYTE),
        ('BatteryFlag', wintypes.BYTE),
        ('BatteryLifePercent', wintypes.BYTE),
        ('Reserved1', wintypes.BYTE),
        ('BatteryLifeTime', wintypes.DWORD),
        ('BatteryFullLifeTime', wintypes.DWORD),
    ]

SYSTEM_POWER_STATUS_P = ctypes.POINTER(SYSTEM_POWER_STATUS)

GetSystemPowerStatus = ctypes.windll.kernel32.GetSystemPowerStatus
GetSystemPowerStatus.argtypes = [SYSTEM_POWER_STATUS_P]
GetSystemPowerStatus.restype = wintypes.BOOL

status = SYSTEM_POWER_STATUS()

def onBattery():
    if not GetSystemPowerStatus(ctypes.pointer(status)):
        raise ctypes.WinError()
    return status.ACLineStatus == 0
    
def batteryPercent():
    if not GetSystemPowerStatus(ctypes.pointer(status)):
        raise ctypes.WinError()
    return status.BatteryLifePercent

def batteryStatus():
    if not GetSystemPowerStatus(ctypes.pointer(status)):
        raise ctypes.WinError()
    return status.BatteryFlag
