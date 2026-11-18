"""Small, reversible Windows settings profile. No shell or service control.

SPDX-License-Identifier: GPL-2.0-or-later
"""
import ctypes
from ctypes import wintypes
import os
import sys
import uuid

DEFAULT_OPTIONS = dict(priority=True, animations=True, power=False, game_mode=False)
HIGH_PERFORMANCE = '8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c'
SETTINGS_PAGES = {
    'captures':'ms-settings:gaming-gamedvr',
    'game_mode':'ms-settings:gaming-gamemode',
    'startup':'ms-settings:startupapps',
    'notifications':'ms-settings:notifications',
    'power':'ms-settings:powersleep',
}
LABELS = {'priority':'OBS scheduling priority', 'window_animation':'Window minimize / maximize animations',
          'client_animation':'Desktop client-area animations', 'power':'High performance power plan',
          'game_mode':'Windows Game Mode preference'}


def options(value=None):
    if value is None:
        return dict(DEFAULT_OPTIONS)
    if not isinstance(value,dict) or set(value)-set(DEFAULT_OPTIONS) or any(not isinstance(v,bool) for v in value.values()):
        raise ValueError('Optimizer choices must be true or false and use supported options.')
    result = {**DEFAULT_OPTIONS, **value}
    if not any(result.values()):
        raise ValueError('Select at least one optimization.')
    return result


def open_settings(page):
    if os.name != 'nt':
        raise ValueError('Windows settings are available in the Windows desktop app.')
    if not isinstance(page,str) or page not in SETTINGS_PAGES:
        raise ValueError('Choose a supported Windows settings page.')
    try:
        os.startfile(SETTINGS_PAGES[page])
    except OSError:
        raise ValueError('Windows could not open that settings page on this PC.')


class WindowsTuning:
    def __init__(self):
        if os.name != 'nt':
            raise OSError('Windows settings are unavailable on this system.')
        self.user = ctypes.WinDLL('user32.dll',winmode=0x800,use_last_error=True)
        self.kernel = ctypes.WinDLL('kernel32.dll',winmode=0x800,use_last_error=True)
        self.power = ctypes.WinDLL('powrprof.dll',winmode=0x800)
        self.user.SystemParametersInfoW.argtypes = [wintypes.UINT,wintypes.UINT,ctypes.c_void_p,wintypes.UINT]
        self.user.SystemParametersInfoW.restype = wintypes.BOOL
        self.power.PowerGetActiveScheme.argtypes = [ctypes.c_void_p,ctypes.POINTER(ctypes.c_void_p)]
        self.power.PowerGetActiveScheme.restype = wintypes.DWORD
        self.power.PowerSetActiveScheme.argtypes = [ctypes.c_void_p,ctypes.c_void_p]
        self.power.PowerSetActiveScheme.restype = wintypes.DWORD
        self.power.PowerEnumerate.argtypes = [ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,wintypes.DWORD,ctypes.c_void_p,ctypes.POINTER(wintypes.DWORD)]
        self.power.PowerEnumerate.restype = wintypes.DWORD
        self.kernel.LocalFree.argtypes = [ctypes.c_void_p]
        self.kernel.LocalFree.restype = ctypes.c_void_p
        class Animation(ctypes.Structure):
            _fields_ = [('cbSize',wintypes.UINT),('iMinAnimate',ctypes.c_int)]
        class PowerStatus(ctypes.Structure):
            _fields_ = [('ACLineStatus',wintypes.BYTE),('BatteryFlag',wintypes.BYTE),('BatteryLifePercent',wintypes.BYTE),('SystemStatusFlag',wintypes.BYTE),('BatteryLifeTime',wintypes.DWORD),('BatteryFullLifeTime',wintypes.DWORD)]
        self.Animation,self.PowerStatus = Animation,PowerStatus
        self.kernel.GetSystemPowerStatus.argtypes = [ctypes.POINTER(PowerStatus)]
        self.kernel.GetSystemPowerStatus.restype = wintypes.BOOL

    def ac_power(self):
        status = self.PowerStatus()
        if not self.kernel.GetSystemPowerStatus(ctypes.byref(status)):
            return False
        return status.ACLineStatus == 1

    def schemes(self):
        result = []
        for index in range(256):
            value,size = ctypes.create_string_buffer(16),wintypes.DWORD(16)
            status = self.power.PowerEnumerate(None,None,None,16,index,value,ctypes.byref(size))
            if status == 259: break  # ERROR_NO_MORE_ITEMS
            if status or size.value != 16: raise OSError('Power plans could not be read.')
            result.append(str(uuid.UUID(bytes_le=value.raw)))
        return result

    def spi(self, action, parameter, value):
        # Change this session's setting and notify apps; do not persist animation preferences.
        if not self.user.SystemParametersInfoW(action,parameter,value,2 if action in (0x49,0x1043) else 0):
            raise ctypes.WinError(ctypes.get_last_error())

    def read(self, setting):
        if setting == 'power':
            pointer = ctypes.c_void_p()
            if self.power.PowerGetActiveScheme(None,ctypes.byref(pointer)):
                raise OSError('The active power plan could not be read.')
            try: return str(uuid.UUID(bytes_le=ctypes.string_at(pointer,16)))
            finally: self.kernel.LocalFree(pointer)
        if setting == 'window_animation':
            value = self.Animation(ctypes.sizeof(self.Animation),0)
            self.spi(0x48,ctypes.sizeof(value),ctypes.byref(value))
            return int(bool(value.iMinAnimate))
        if setting == 'client_animation':
            value = wintypes.BOOL()
            self.spi(0x1042,0,ctypes.byref(value))
            return int(bool(value.value))
        if setting == 'game_mode':
            if sys.getwindowsversion().build < 22000:
                raise OSError('Automatic Game Mode preference control requires Windows 11. Use Open Game Mode settings on this PC.')
            import winreg
            try:
                with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\GameBar') as key:
                    value,kind = winreg.QueryValueEx(key,'AutoGameModeEnabled')
                    if kind != winreg.REG_DWORD or value not in (0,1):
                        raise OSError('Windows Game Mode has a custom value; keep it unchanged and review Windows Settings.')
                    return value
            except FileNotFoundError: return None
        raise ValueError('Unsupported Windows optimization setting.')

    def write(self, setting, value):
        if setting == 'power':
            raw = ctypes.create_string_buffer(uuid.UUID(str(value)).bytes_le)
            if self.power.PowerSetActiveScheme(None,raw):
                raise OSError('Windows did not allow changing the power plan.')
        elif setting == 'window_animation':
            if value not in (0,1): raise ValueError('Invalid animation setting.')
            animation = self.Animation(ctypes.sizeof(self.Animation),int(value))
            self.spi(0x49,ctypes.sizeof(animation),ctypes.byref(animation))
        elif setting == 'client_animation':
            if value not in (0,1): raise ValueError('Invalid animation setting.')
            self.spi(0x1043,0,ctypes.c_void_p(int(value)))
        elif setting == 'game_mode':
            if sys.getwindowsversion().build < 22000: raise OSError('Automatic Game Mode preference control requires Windows 11.')
            import winreg
            if value is None:
                try:
                    with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\GameBar',0,winreg.KEY_SET_VALUE) as key:
                        winreg.DeleteValue(key,'AutoGameModeEnabled')
                except FileNotFoundError: pass
            elif value in (0,1):
                with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\GameBar',0,winreg.KEY_SET_VALUE) as key:
                    winreg.SetValueEx(key,'AutoGameModeEnabled',0,winreg.REG_DWORD,int(value))
            else: raise ValueError('Invalid Game Mode preference.')
        else: raise ValueError('Unsupported Windows optimization setting.')

    def prepare(self, selected):
        records = []
        for setting, applied in [('window_animation',0),('client_animation',0),('power',HIGH_PERFORMANCE),('game_mode',1)]:
            chosen = selected['animations'] if setting.endswith('animation') else selected[setting]
            if not chosen: continue
            if setting == 'power':
                if not self.ac_power():
                    raise ValueError('High performance power requires confirmed plugged-in power. Uncheck it to continue on battery.')
                if HIGH_PERFORMANCE not in self.schemes():
                    raise ValueError('This PC has no High performance plan. Uncheck that option; FDGCast does not create or force a plan.')
            original = self.read(setting)
            if original != applied:
                records.append(dict(kind='windows',setting=setting,original=original,applied=applied))
        return records
