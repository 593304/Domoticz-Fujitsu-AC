# Domoticz-Fujitsu-AC
Fujitsu air conditioner (FGLair) Plugin for Domoticz.

## Prerequisites
### pyfujitsu library
This module is using [Mmodarre's pyfujitsu library](https://github.com/Mmodarre/pyfujitsu). Install this module by running this command: `pip3 install pyfujitsu`.  

## Installation
Connect to your Domoticz server via SSH and go to Domoticz's plugins directory. Clone this repository into the plugins directory:  
`git clone https://github.com/593304/Domoticz-Fujitsu-AC.git`  
If necessary modify the access permissions for the plugin. For example:  
`chmod -R 777 Domoticz-Fujitsu-AC/`  
Then restart Domoticz service to add the Fujitsu AC plugin to the hardware list in Domoticz.
```
sudo /etc/init.d/domoticz.sh stop
sudo /etc/init.d/domoticz.sh start
```
OR  
```
sudo service domoticz.sh stop
sudo service domoticz.sh start
```

## Configuration
If Domoticz started, then go to the Hardware page on your Domoticz website and add a new one. You should find the Fujitsu AC Plugin in the Type list. Select it and set the following values:
   - Username (the email address of your FGLair account)
   - Password (the password for your FGLair account)
   - Region (your region(EU, CN or other))
   - Debug (you cn turn on or off debug messages)
