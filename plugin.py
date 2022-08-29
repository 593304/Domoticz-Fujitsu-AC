# Fujitsu AC Plugin
#
# Author: 593304
#
"""
<plugin key="FujitsuACPlugin" name="Fujitsu AC Plugin" author="593304" version="0.4" externallink="https://github.com/593304/Domoticz-Fujitsu-AC">
    <description>
        <h2>Fujitsu AC Plugin</h2><br/>
        <p>The plugin will connect to the cloud solution behind the FGLair app to control your air conditioner. The FGLair app's username(e-mail address) and password is necessary.</p>
        <p>Before using this plugin, you have to install the<a href="https://github.com/Mmodarre/pyfujitsu" style="margin-left: 5px">pyfujitsu module</a></p>
        <br />
        <br />
    </description>
    <params>
        <param field="Mode1" label="Username" width="250px" required="true"/>
        <param field="Password" label="Password" width="250px" required="true" password="true"/>
        <param field="Mode2" label="Region" width="100px">
            <options>
                <option label="EU" value="eu" default="eu"/>
                <option label="CN" value="cn"/>
                <option label="Other" value="other"/>
            </options>
        </param>
        <param field="Mode3" label="Refresh interval" width="100px">
            <options>
                <option label="5" value="5"/>
                <option label="10" value="10" default="10"/>
                <option label="20" value="20"/>
                <option label="30" value="30"/>
                <option label="45" value="45"/>
                <option label="60" value="60"/>
                <option label="90" value="90"/>
                <option label="120" value="120"/>
                <option label="150" value="150"/>
                <option label="180" value="180"/>
            </options>
        </param>
        <param field="Mode4" label="Debug" width="50px">
            <options>
                <option label="On" value="on"/>
                <option label="Off" value="off" default="off"/>
            </options>
        </param>
    </params>
</plugin>
"""
import Domoticz
from pyfujitseu import splitAC

import os
import tempfile

DATABASE_KEY = "FujitsuACPlugin"


# Configuration Helpers
def getConfigItem():
    value = {}
    try:
        config = Domoticz.Configuration()
        value = config[DATABASE_KEY]
    except KeyError:
        value = {}
    except Exception as inst:
        Domoticz.Error("Domoticz.Configuration read failed: '%s'" % (str(inst)))
    return value
    

def setConfigItem(value):
    config = {}
    try:
        config = Domoticz.Configuration()
        config[DATABASE_KEY] = value
        config = Domoticz.Configuration(config)
    except Exception as inst:
        Domoticz.Error("Domoticz.Configuration operation failed: '%s'" % (str(inst)))
    return config


# Simple heartbeat with 5-180 secs interval
class Heartbeat:
    def __init__(self, interval):
        self.callback = None
        self.interval = interval
        self.heartbeatRate = 15
        self.heartbeatRoundCounter = 0
        self.heartbeatRound = self.interval / self.heartbeatRate

    def setHeartbeat(self, callback):
        if self.interval > 30:
            Domoticz.Heartbeat(self.heartbeatRate)
        else:
            Domoticz.Heartbeat(self.interval)
        Domoticz.Log("Heartbeat interval is %s seconds" % (str(self.interval)))
        self.callback = callback
            
    def beatHeartbeat(self):
        callbackEnabled = False
        if self.interval > 30:
            self.heartbeatRoundCounter += 1
            if self.heartbeatRoundCounter == int(self.heartbeatRound):
                callbackEnabled = True
                self.heartbeatRoundCounter = 0
        else:
            callbackEnabled = True

        if callbackEnabled:
            self.callback()


class Helper:
    def __init__(self, username, password, region):
        self.username = username
        self.password = password
        self.region = region
        self.acs = {}
        self.usedUnitClasses = []
        self.databaseStore = {}
        self.units = {}
        self.selectorData = {}

        self.token_memory_file_name = None
        return
    
    def _getNextUnitClass(self):
        unitClass = 0
        while unitClass in self.usedUnitClasses:
            unitClass += 11
        return unitClass

    def _addAcToList(self, dsn, api, unitClass):
        ac = splitAC.splitAC(dsn, api)
        Domoticz.Debug("  - %s - %s" % (dsn, ac.device_name["value"]))
        self.usedUnitClasses.append(unitClass)
        self.acs[dsn] = {
            "ac": ac,
            "unitClass": unitClass
        }
        self.databaseStore[dsn] = unitClass
    
    def get_api(self):
        if self.token_memory_file_name is None:
            self.token_memory_file_name = tempfile.NamedTemporaryFile(delete=False).name
        return splitAC.api(self.username, self.password, self.region, tokenpath=self.token_memory_file_name)

    def clean_up(self):
        if self.token_memory_file_name is not None:
            os.unlink(self.token_memory_file_name)

    def getAcs(self):
        api = self.get_api()
        dsns = api.get_devices_dsn()
        Domoticz.Log("Connected to FGLair API and found %d device(s) for %s" % (len(dsns), self.username))

        Domoticz.Log("Checking database for saved devices ...")
        storedData = getConfigItem()
        Domoticz.Log("Found %d devices in the database, removing old ones ..." % (len(storedData)))
        existingDsns = []
        for dsn in storedData:
            if dsn in dsns:
                existingDsns.append(dsn)
        Domoticz.Log("Found %d existing devices in the list" % (len(existingDsns)))

        Domoticz.Debug("The existing device(s):")
        for dsn in existingDsns:
            self._addAcToList(dsn, api, storedData[dsn])
        
        Domoticz.Debug("The new device(s):")
        for dsn in dsns:
            if dsn not in existingDsns:
                self._addAcToList(dsn, api, self._getNextUnitClass())
        
        setConfigItem(self.databaseStore)
        
        return
    
    def updateAcs(self):
        api = self.get_api()
        dsns = api.get_devices_dsn()
        foundNewDevice = False
        for dsn in dsns:
            if dsn not in self.acs:
                foundNewDevice = True
                Domoticz.Log("Found a new device(%s) while was updating the properties" % (dsn))
                self._addAcToList(dsn, api, self._getNextUnitClass())
                self.createDomoticzDevices(dsn)
        
        if foundNewDevice:
            setConfigItem(self.databaseStore)

        for dsn in self.acs:
            self.acs[dsn]["ac"].refresh_properties()
            Domoticz.Debug("Refreshing properties: %s - %s" % (dsn, self.acs[dsn]["ac"].device_name["value"]))
        return
    
    def createDomoticzDevices(self, dsn):
        name = self.acs[dsn]["ac"].device_name["value"]
        unitClass = self.acs[dsn]["unitClass"]
        verticalDirection = self.acs[dsn]["ac"].af_vertical_direction

        Domoticz.Log("Creating devices in Domoticz for %s - %s" % (dsn, name))

        unit = unitClass + 1
        if unit not in Devices:
            Domoticz.Debug("%s - Creating power switch" % (dsn))
            Domoticz.Device(Name="%s - Power"%(name), Unit=unit, Image=16, TypeName="Switch").Create()
        else:
            Domoticz.Debug("%s - Power switch already exists with unit ID: %d" % (dsn, unit))
        self.units[unit] = {
            "type": "switch",
            "dsn": dsn,
            "command": self.powerSwitch,
            "update": self.updateDomoticzDevice,
            "currentValue": self.powerSwitchCurrentValue,
            "dependantSwitch": {
                "unit": unitClass + 3,
                "ifValue": "off",
                "setValue": 10
            }
        }

        unit = unitClass + 2
        if unit not in Devices:
            Domoticz.Debug("%s - Creating tempretature selector switch" % (dsn))
            Options = {"LevelActions" : "|||||||||||||||||||||||||||||",
                    "LevelNames" : "|18|18.5|19|19.5|20|20.5|21|21.5|22|22.5|23|23.5|24|24.5|25|25.5|26|26.5|27|27.5|28|28.5|29|29.5|30|30.5|31|31.5|32",
                    "LevelOffHidden" : "true",
                    "SelectorStyle" : "1"}
            Domoticz.Device(Name="%s - Temperature selector"%(name), Unit=unit, Image=16, TypeName="Selector Switch", Options=Options).Create()
        else:
            Domoticz.Debug("%s - Temperature selector switch already exists with unit ID: %d" % (dsn, unit))
        self.units[unit] = {
            "type": "selector",
            "dsn": dsn,
            "command": self.temperatureSelectorSwitch,
            "update": self.updateDomoticzDevice,
            "currentValue": self.temperatureSelectorSwitchCurrentValue
        }
        self.selectorData[unit] = {
            "18.0": 10,  "18.5": 20,  "19.0": 30,  "19.5": 40,
            "20.0": 50,  "20.5": 60,  "21.0": 70,  "21.5": 80,
            "22.0": 90,  "22.5": 100, "23.0": 110, "23.5": 120,
            "24.0": 130, "24.5": 140, "25.0": 150, "25.5": 160,
            "26.0": 170, "26.5": 180, "27.0": 190, "27.5": 200,
            "28.0": 210, "28.5": 220, "29.0": 230, "29.5": 240,
            "30.0": 250, "30.5": 260, "31.0": 270, "31.5": 280, "32": 290,
            "10": 18,  "20": 18.5,  "30": 19,  "40": 19.5,
            "50": 20,  "60": 20.5,  "70": 21,  "80": 21.5,
            "90": 22,  "100": 22.5, "110": 23, "120": 23.5,
            "130": 24, "140": 24.5, "150": 25, "160": 25.5,
            "170": 26, "180": 26.5, "190": 27, "200": 27.5,
            "210": 28, "220": 28.5, "230": 29, "240": 29.5,
            "250": 30, "260": 30.5, "270": 31, "280": 31.5, "290": 32
        }

        unit = unitClass + 3
        if unit not in Devices:
            Domoticz.Debug("%s - Creating operation selector switch" % (dsn))
            Options = {"LevelActions" : "||||||",
                    "LevelNames" : "|Off|Auto|Cool|Dry|Fan only|Heat",
                    "LevelOffHidden" : "true",
                    "SelectorStyle" : "1"}
            Domoticz.Device(Name="%s - Operation selector"%(name), Unit=unit, Image=16, TypeName="Selector Switch", Options=Options).Create()
        else:
            Domoticz.Debug("%s - Operation selector switch already exists with unit ID: %d" % (dsn, unit))
        self.units[unit] = {
            "type": "selector",
            "dsn": dsn,
            "command": self.operationSelectorSwitch,
            "update": self.updateDomoticzDevice,
            "currentValue": self.operationSelectorSwitchCurrentValue
        }
        self.selectorData[unit] = {
            "off": 10,   "auto": 20,       "cool": 30,
            "dry": 40,   "fan only": 50,   "heat": 60,
            "10": "Off", "20": "Auto",     "30": "Cool",
            "40": "Dry", "50": "Fan only", "60": "Heat"
        }

        unit = unitClass + 4
        if unit not in Devices:
            Domoticz.Debug("%s - Creating economy switch" % (dsn))
            Domoticz.Device(Name="%s - Economy"%(name), Unit=unit, Image=16, TypeName="Switch").Create()
        else:
            Domoticz.Debug("%s - Economy switch already exists with unit ID: %d" % (dsn, unit))
        self.units[unit] = {
            "type": "switch",
            "dsn": dsn,
            "command": self.economySwitch,
            "update": self.updateDomoticzDevice,
            "currentValue": self.economySwitchCurrentValue
        }

        unit = unitClass + 5
        if unit not in Devices:
            Domoticz.Debug("%s - Creating powerfull mode switch" % (dsn))
            Domoticz.Device(Name="%s - Powerfull mode"%(name), Unit=unit, Image=16, TypeName="Switch").Create()
        else:
            Domoticz.Debug("%s - Powerfull mode switch already exists with unit ID: %d" % (dsn, unit))
        self.units[unit] = {
            "type": "switch",
            "dsn": dsn,
            "command": self.powerfullModeSwitch,
            "update": self.updateDomoticzDevice,
            "currentValue": self.powerfullModeSwitchCurrentValue
        }

        unit = unitClass + 6
        if unit not in Devices:
            Domoticz.Debug("%s - Creating fan speed switch" % (dsn))
            Options = {"LevelActions" : "|||||",
                    "LevelNames" : "|Quiet|Low|Medium|High|Auto",
                    "LevelOffHidden" : "true",
                    "SelectorStyle" : "1"}
            Domoticz.Device(Name="%s - Fan speed"%(name), Unit=unit, Image=16, TypeName="Selector Switch", Options=Options).Create()
        else:
            Domoticz.Debug("%s - Fan speed switch already exists with unit ID: %d" % (dsn, unit))
        self.units[unit] = {
            "type": "selector",
            "dsn": dsn,
            "command": self.fanSpeedSwitch,
            "update": self.updateDomoticzDevice,
            "currentValue": self.fanSpeedSwitchCurrentValue
        }
        self.selectorData[unit] = {
            "quiet": 10,   "low": 20,   "medium": 30,
            "high": 40,    "auto": 50,
            "10": "Quiet", "20": "Low", "30": "Medium",
            "40": "High",  "50": "Auto"
        }

        unit = unitClass + 7
        if unit not in Devices:
            Domoticz.Debug("%s - Creating vertical swing switch" % (dsn))
            Domoticz.Device(Name="%s - Vertical swing"%(name), Unit=unit, Image=16, TypeName="Switch").Create()
        else:
            Domoticz.Debug("%s - Vertical swing switch already exists with unit ID: %d" % (dsn, unit))
        self.units[unit] = {
            "type": "switch",
            "dsn": dsn,
            "command": self.verticalSwingSwitch,
            "update": self.updateDomoticzDevice,
            "currentValue": self.verticalSwingSwitchCurrentValue
        }

        unit = unitClass + 8
        if unit not in Devices:
            Domoticz.Debug("%s - Creating horizontal swing switch" % (dsn))
            Domoticz.Device(Name="%s - Horizontal swing"%(name), Unit=unit, Image=16, TypeName="Switch").Create()
        else:
            Domoticz.Debug("%s - Horizontal swing switch already exists with unit ID: %d" % (dsn, unit))
        self.units[unit] = {
            "type": "switch",
            "dsn": dsn,
            "command": self.horizontalSwingSwitch,
            "update": self.updateDomoticzDevice,
            "currentValue": self.horizontalSwingSwitchCurrentValue
        }

        if verticalDirection != None:
            unit = unitClass + 9
            if unit not in Devices:
                Domoticz.Debug("%s - Creating swing mode switch" % (dsn))
                Options = {"LevelActions" : "||||",
                        "LevelNames" : "|Horizontal|Down|Unknown|Swing",
                        "LevelOffHidden" : "true",
                        "SelectorStyle" : "1"}
                Domoticz.Device(Name="%s - Swing mode"%(name), Unit=unit, Image=16, TypeName="Selector Switch", Options=Options).Create()
            else:
                Domoticz.Debug("%s - Swing mode switch already exists with unit ID: %d" % (dsn, unit))
            self.units[unit] = {
                "type": "selector",
                "dsn": dsn,
                "command": self.swingModeSwitch,
                "update": self.updateDomoticzDevice,
                "currentValue": self.swingModeSwitchCurrentValue
            }
            self.selectorData[unit] = {
                "Horizontal": 10,   "Down": 20,
                "Unknown": 30,      "Swing": 40,
                "10": "Horizontal", "20": "Down",
                "30": "Unknown",    "40": "Swing"
            }

            unit = unitClass + 10
            if unit not in Devices:
                Domoticz.Debug("%s - Creating vertical direction switch" % (dsn))
                Options = {"LevelActions" : "|||||||",
                        "LevelNames" : "|1|2|3|4|5|6|7",
                        "LevelOffHidden" : "true",
                        "SelectorStyle" : "1"}
                Domoticz.Device(Name="%s - Vertical direction"%(name), Unit=unit, Image=16, TypeName="Selector Switch", Options=Options).Create()
            else:
                Domoticz.Debug("%s - Vertical direction switch already exists with unit ID: %d" % (dsn, unit))
            self.units[unit] = {
                "type": "selector",
                "dsn": dsn,
                "command": self.verticalDirectionSwitch,
                "update": self.updateDomoticzDevice,
                "currentValue": self.verticalDirectionSwitchCurrentValue
            }
            self.selectorData[unit] = {
                "1": 10, "2": 20, "3": 30, "4": 40,
                "5": 50, "6": 60, "7": 70,
                "10": 1, "20": 2, "30": 3, "40": 4,
                "50": 5, "60": 6, "70": 7
            }
            
            unit = unitClass + 11
            if unit not in Devices:
                Domoticz.Debug("%s - Creating horizontal direction switch" % (dsn))
                Options = {"LevelActions" : "|||||||",
                        "LevelNames" : "|1|2|3|4|5|6|7",
                        "LevelOffHidden" : "true",
                        "SelectorStyle" : "1"}
                Domoticz.Device(Name="%s - Horizontal direction"%(name), Unit=unit, Image=16, TypeName="Selector Switch", Options=Options).Create()
            else:
                Domoticz.Debug("%s - Horizontal direction switch already exists with unit ID: %d" % (dsn, unit))
            self.units[unit] = {
                "type": "selector",
                "dsn": dsn,
                "command": self.horizontalDirectionSwitch,
                "update": self.updateDomoticzDevice,
                "currentValue": self.horizontalDirectionSwitchCurrentValue
            }
            self.selectorData[unit] = {
                "1": 10, "2": 20, "3": 30, "4": 40,
                "5": 50, "6": 60, "7": 70,
                "10": 1, "20": 2, "30": 3, "40": 4,
                "50": 5, "60": 6, "70": 7
            }
        return

    def initializeDomoticz(self):
        Domoticz.Log("Creating devices in Domoticz")
        for dsn in self.acs:
            self.createDomoticzDevices(dsn)
        return

    def runCommand(self, unit, command, level):
        dsn = self.units[unit]["dsn"]
        updateValues = self.units[unit]["command"](unit, dsn, command, str(level))
        self.units[unit]["update"](unit, updateValues["nValue"], updateValues["sValue"])
        if "dependantSwitch" in self.units[unit] and self.units[unit]["dependantSwitch"]["ifValue"] == updateValues["sValue"].lower():
            self.updateDomoticzDevice(self.units[unit]["dependantSwitch"]["unit"], updateValues["nValue"], self.units[unit]["dependantSwitch"]["setValue"])
        return
    
    def powerSwitchCurrentValue(self, dsn):
        return self.acs[dsn]["ac"].operation_mode_desc

    def powerSwitch(self, unit, dsn, command, level):
        ac = self.acs[dsn]["ac"]
        nValue = 0
        sValue = "Off"
        if command.lower() == "on":
            ac.turnOn()
            nValue = 1
            sValue = "On"
        else:
            ac.turnOff()
        return {
            "nValue": nValue,
            "sValue": sValue
        }
    
    def temperatureSelectorSwitchCurrentValue(self, dsn):
        return self.acs[dsn]["ac"].adjust_temperature_degree

    def temperatureSelectorSwitch(self, unit, dsn, command, level):
        ac = self.acs[dsn]["ac"]
        ac.refresh_properties()
        om = ac.operation_mode_desc
        nValue = 0 if om.lower() == "off" else 1
        sValue = self.selectorData[unit][level]
        ac.changeTemperature(float(sValue))
        return {
            "nValue": nValue,
            "sValue": level
        }
    
    def operationSelectorSwitchCurrentValue(self, dsn):
        return self.acs[dsn]["ac"].operation_mode_desc
    
    def operationSelectorSwitch(self, unit, dsn, command, level):
        ac = self.acs[dsn]["ac"]
        ac.refresh_properties()
        om = ac.operation_mode_desc
        nValue = 0 if om.lower() == "off" else 1
        sValue = self.selectorData[unit][level]
        if sValue == "Fan only":
            sValue = "fan_only"
        ac.changeOperationMode(sValue)
        return {
            "nValue": nValue,
            "sValue": level
        }
    
    def economySwitchCurrentValue(self, dsn):
        return "On" if self.acs[dsn]["ac"].economy_mode["value"] else "Off"
    
    def economySwitch(self, unit, dsn, command, level):
        ac = self.acs[dsn]["ac"]
        nValue = 0
        sValue = "Off"
        if command.lower() == "on":
            ac.economy_mode_on()
            nValue = 1
            sValue = "On"
        else:
            ac.economy_mode_off()
        return {
            "nValue": nValue,
            "sValue": sValue
        }
    
    def powerfullModeSwitchCurrentValue(self, dsn):
        return "On" if self.acs[dsn]["ac"].powerful_mode["value"] else "Off"
    
    def powerfullModeSwitch(self, unit, dsn, command, level):
        ac = self.acs[dsn]["ac"]
        nValue = 0
        sValue = "Off"
        if command.lower() == "on":
            ac.powerfull_mode_on()
            nValue = 1
            sValue = "On"
        else:
            ac.powerfull_mode_off()
        return {
            "nValue": nValue,
            "sValue": sValue
        }
    
    def fanSpeedSwitchCurrentValue(self, dsn):
        return self.acs[dsn]["ac"].get_fan_speed_desc()
    
    def fanSpeedSwitch(self, unit, dsn, command, level):
        ac = self.acs[dsn]["ac"]
        ac.refresh_properties()
        om = ac.operation_mode_desc
        nValue = 0 if om.lower() == "off" else 1
        sValue = self.selectorData[unit][level]
        ac.changeFanSpeed(sValue)
        return {
            "nValue": nValue,
            "sValue": level
        }
    
    def verticalSwingSwitchCurrentValue(self, dsn):
        return "On" if self.acs[dsn]["ac"].af_vertical_swing["value"] else "Off"
    
    def verticalSwingSwitch(self, unit, dsn, command, level):
        ac = self.acs[dsn]["ac"]
        nValue = 0
        sValue = "Off"
        if command.lower() == "on":
            ac.vertical_swing_on()
            nValue = 1
            sValue = "On"
        else:
            ac.vertical_swing_off()
        return {
            "nValue": nValue,
            "sValue": sValue
        }
    
    def horizontalSwingSwitchCurrentValue(self, dsn):
        return "On" if self.acs[dsn]["ac"].af_horizontal_swing["value"] else "Off"
    
    def horizontalSwingSwitch(self, unit, dsn, command, level):
        ac = self.acs[dsn]["ac"]
        nValue = 0
        sValue = "Off"
        if command.lower() == "on":
            ac.horizontal_swing_on()
            nValue = 1
            sValue = "On"
        else:
            ac.horizontal_swing_off()
        return {
            "nValue": nValue,
            "sValue": sValue
        }
    
    def swingModeSwitchCurrentValue(self, dsn):
        return self.acs[dsn]["ac"].get_swing_mode_desc
    
    def swingModeSwitch(self, unit, dsn, command, level):
        ac = self.acs[dsn]["ac"]
        ac.refresh_properties()
        om = ac.operation_mode_desc
        nValue = 0 if om.lower() == "off" else 1
        sValue = self.selectorData[unit][level]
        ac.changeSwingMode(sValue)
        return {
            "nValue": nValue,
            "sValue": level
        }

    def verticalDirectionSwitchCurrentValue(self, dsn):
        return self.acs[dsn]["ac"].af_vertical_direction["value"]
    
    def verticalDirectionSwitch(self, unit, dsn, command, level):
        ac = self.acs[dsn]["ac"]
        ac.refresh_properties()
        om = ac.operation_mode_desc
        nValue = 0 if om.lower() == "off" else 1
        sValue = self.selectorData[unit][level]
        ac.vertical_direction(int(sValue))
        return {
            "nValue": nValue,
            "sValue": level
        }
    
    def horizontalDirectionSwitchCurrentValue(self, dsn):
        return self.acs[dsn]["ac"].af_horizontal_direction["value"]
    
    def horizontalDirectionSwitch(self, unit, dsn, command, level):
        ac = self.acs[dsn]["ac"]
        ac.refresh_properties()
        om = ac.operation_mode_desc
        nValue = 0 if om.lower() == "off" else 1
        sValue = self.selectorData[unit][level]
        ac.horizontal_direction(int(sValue))
        return {
            "nValue": nValue,
            "sValue": level
        }
    
    def updateDomoticzDevice(self, unit, nValue, sValue):
        Domoticz.Debug("Updating Domoticz device %s/%d: (%d,%s)" % (self.units[unit]["dsn"], unit, nValue, sValue))
        Devices[unit].Update(nValue = nValue, sValue = str(sValue))
    
    def updateDomoticzDevices(self):
        for unit in self.units:
            dsn = self.units[unit]["dsn"]
            unitType = self.units[unit]["type"]
            value = self.units[unit]["currentValue"](dsn)
            om = self.acs[dsn]["ac"].operation_mode_desc
            
            nValue = 0 if om.lower() == "off" else 1
            sValue = value
            if unitType == "switch":
                nValue = 0 if value.lower() == "off" else 1
                sValue = "On" if sValue else "Off"
            if isinstance(sValue, str) and "fan" in sValue.lower():
            	sValue = "Fan only"
            if unit in self.selectorData and (str(sValue)).lower() in self.selectorData[unit]:
                sValue = self.selectorData[unit][(str(sValue)).lower()]

            self.updateDomoticzDevice(unit, nValue, sValue)
        return


class FujitsuACPlugin:
    def __init__(self):
        self.devices = {}
        self.lastState = None
        self.heartbeat = None
        self.helper = None
        return

    def onStart(self):
        Domoticz.Log("onStart called")
        
        # Setting up debug mode
        if (Parameters["Mode4"] != "off"):
            Domoticz.Debugging(1)
            Domoticz.Debug("Debug mode enabled")

        # Setting up heartbeat
        self.heartbeat = Heartbeat(int(Parameters["Mode3"]))
        self.heartbeat.setHeartbeat(self.update)

        # Setting up helper
        Domoticz.Log("Mode1: %s, Password: %s, Mode2: %s" % (Parameters["Mode1"], Parameters["Password"], Parameters["Mode2"]))
        self.helper = Helper(Parameters["Mode1"], Parameters["Password"], Parameters["Mode2"])

        # Getting air conditioners
        self.helper.getAcs()

        # Creating Domoticz devices
        self.helper.initializeDomoticz()

        #Updating Domoticz devices
        self.update()

        DumpConfigToLog()

        return

    def onStop(self):
        Domoticz.Log("onStop called")
        self.helper.clean_up()
        return

    def onConnect(self, Connection, Status, Description):
        Domoticz.Log("onConnect called; connection: %s, status: %s, description: %s" % (str(Connection), str(Status), str(Description)))
        return

    def onMessage(self, Connection, Data):
        Domoticz.Log("onMessage called; connection: %s, data: %s" % (str(Connection), str(Data)))
        return

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Log("onCommand called for Unit: %d, Parameter: '%s', Level: '%s'" % (Unit, str(Command), str(Level)))
        self.helper.runCommand(Unit, Command, Level)
        return

    def onNotification(self, Name, Subject, Text, Status, Priority, Sound, ImageFile):
        Domoticz.Log("Notification: " + Name + "," + Subject + "," + Text + "," + Status + "," + str(Priority) + "," + Sound + "," + ImageFile)
        return

    def onDisconnect(self, Connection):
        Domoticz.Log("onDisconnect called")
        return

    def onHeartbeat(self):
        Domoticz.Debug("onHeartbeat called")
        self.heartbeat.beatHeartbeat()
        return

    def update(self):
        Domoticz.Debug("update called")
        self.helper.updateAcs()
        self.helper.updateDomoticzDevices()
        return


global _plugin
_plugin = FujitsuACPlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return
