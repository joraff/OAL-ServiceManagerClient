#!/usr/bin/env python

import sys, os
import httplib                      # to connect to our http SOAP service
from xml.dom import minidom         # to be able to read the service's response
from xml.sax.saxutils import escape # to properly escape our XML values
from subprocess import call, Popen, PIPE, STDOUT         # for the ability to use cmdline utilities to obtain system information
import signal
import commands
import re
import time 

debug = True
#######################################
# XML Templates for the body of our SOAP request.
# Each %s should be replaced with the appropriate values before sending.
#######################################

loginRequestTemplate = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <UpdateDatabaseWithLoginLogoutDataMac xmlns="http://oalinfo.tamu.edu/tools/ServiceManager/">
      <Key>thisisakeyforthemacs</Key>
      <UserName>%(username)s</UserName>
      <IPAddress>%(ipAddress)s</IPAddress>
      <MACAddress>%(macAddress)s</MACAddress>
      <ComputerName>%(computerName)s</ComputerName>
      <LogonServer>%(logonServer)s</LogonServer>
      <LoginORLogout>%(loginOrLogout)s</LoginORLogout>
      <UpdateTime>%(updateTime)s</UpdateTime>
    </UpdateDatabaseWithLoginLogoutDataMac>
  </soap:Body>
</soap:Envelope>"""

startupRequestTemplate = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <UpdateDatabaseWithStartupShutdownMac xmlns="http://oalinfo.tamu.edu/tools/ServiceManager/">
      <Key>thisisakeyforthemacs</Key>
      <ComputerName>%(computerName)s</ComputerName>
      <IPAddress>%(ipAddress)s</IPAddress>
      <MACAddress>%(macAddress)s</MACAddress>
      <StartupOrShutdown>%(startupOrShutdown)s</StartupOrShutdown>
      <UpdateTime>%(updateTime)s</UpdateTime>
    </UpdateDatabaseWithStartupShutdownMac>
  </soap:Body>
</soap:Envelope>"""



#######################################
# Method that handles logging process progress
#######################################
            
def log(s):
    localtime = time.asctime( time.localtime(time.time()) )
    print s
    with open("/Library/Logs/OAL Service Manager.log", "a") as f:
         f.write(localtime+": "+s+"\n")



#######################################
# Class that handles obtaining our current system's various bits of information
#######################################

class SystemInfo:
    networkWaitTime = 0
    
    def __init__(self):
        """Init our object with the system information attributes we need"""
        self.update()

    def update(self):
        """Update ourselves with the latest system information"""
        # Use scutil (System Configuration Utility) to query configd for our ComputerName
        self.computerName = commands.getstatusoutput("scutil --get ComputerName")[1]
        
        # Use the id(1) utility to get the username of the calling user (NetID or root)
        self.username = commands.getstatusoutput("id -un")[1]
        
        # Obtain the primary interface by grabbing the first en(i) device listed in the service order.
        try:
            p = Popen(['scutil'], stdout=PIPE, stdin=PIPE, stderr=STDOUT)
            stdout = p.communicate(input='open\nget State:/Network/Global/IPv4\nd.show\nquit\n')[0]
            primaryInt = re.search("PrimaryInterface : (.*)", stdout).group(1)
        except AttributeError, e:
            log("No active network addresses to handle event %s. Waiting 10 seconds before trying again (elapsed time=%s)" % (eventType, self.networkWaitTime))
            if self.networkWaitTime < 30:
                time.sleep(10)
                self.networkWaitTime += 10
                self.update()
            else:
                log("No active network address ever found. Sending empty IP data, and en0 mac address")
                self.ipAddress = ""
                self.macAddress = commands.getstatusoutput("ifconfig en0 | grep 'ether' | awk {'print $2'}")[1]
        else:
            self.ipAddress = commands.getstatusoutput("ifconfig %s | grep 'inet ' | awk {'print $2'}" % (primaryInt))[1]
            self.macAddress = commands.getstatusoutput("ifconfig %s | grep 'ether' | awk {'print $2'}" % (primaryInt))[1]



# Instantiate a global System Information object. Some of this information won't be available at shutdown.
sysinfo = SystemInfo()
if debug: log("Got past systemInfo")



#######################################
# Special method to handle the fact a network address might not be available at runtime
#######################################

def network_up(nowait=False):
    """Returns a boolean based on whether we have an active network interface"""
    try:
        p = Popen(['scutil'], stdout=PIPE, stdin=PIPE, stderr=STDOUT)
        stdout = p.communicate(input='open\nget State:/Network/Global/IPv4\nd.show\nquit\n')[0]
        primaryInt = re.search("PrimaryInterface : (.*)", stdout).group(1)
    except AttributeError, e:
        return False
    else:
        return True



#######################################
# Method that actually ships off the SOAP request
#######################################
            
def do_soap_operation(headers, request, requestMap):
    
    # Merge our keys into the request template
    request = request % requestMap
    if debug: log("mapped request")
    # Open connection to the service
    connection = httplib.HTTPConnection("oalinfo.tamu.edu", 80)
    if debug: log("opened connection")
    # Send our request, complete with the headers and body, and save the response
    connection.request("POST", "/tools/servicemanager/servicemanager.asmx", request, headers)
    if debug: log("sent request")
    response = connection.getresponse()
    if debug: log("got response")
    document = minidom.parseString(response.read())
    if response.status != 200:
        log("Error code from the service manager: %d" % (response.status))



#######################################
# Method that handles preparing the SOAP operation for the various event types
#######################################
    
def do_system_event(eventType):
    """Obtains the system data values and places them into the SOAP request template"""
    if debug: log("Handling a %s event"%(eventType))
    
    if eventType in ['login', 'logout']:
        requestMap = {
            'username':escape(sysinfo.username),
            'computerName':escape(sysinfo.computerName),
            'ipAddress':escape(sysinfo.ipAddress),
            'macAddress':escape(sysinfo.macAddress),
            'logonServer':escape("")
        }
        # LoginOrLogout key: True for a login event, false for a logout event
        requestMap['loginOrLogout'] = "true" if eventType == 'login' else "false"
        headers = {
            'Host':'oalinfo.tamu.edu',
            'Content-Type':'text/xml; charset=utf-8',
            'SOAPAction':"http://oalinfo.tamu.edu/tools/ServiceManager/UpdateDatabaseWithLoginLogoutDataMac"
        }
        if network_up():
            do_soap_operation(headers, loginRequestTemplate, requestMap)
        else:
            if debug: log("Network detected to be down, skipping request")
        
    elif eventType in ['startup', 'shutdown']:
        requestMap = {
            'computerName':escape(sysinfo.computerName),
            'ipAddress':escape(sysinfo.ipAddress),
            'macAddress':escape(sysinfo.macAddress)
        }
        # StartupOrShutdown key: True for a startup event, false for a shutdown event
        requestMap['startupOrShutdown'] = "true" if eventType == 'startup' else "false"
        headers = {
            'Host':'oalinfo.tamu.edu',
            'Content-Type':'text/xml; charset=utf-8',
            'SOAPAction':"http://oalinfo.tamu.edu/tools/ServiceManager/UpdateDatabaseWithStartupShutdownMac"}
        do_soap_operation(headers, startupRequestTemplate, requestMap)
    
    log("Servicemanager client successfully sent %s event"%(eventType))


#######################################
# Method to handle the SIGTERM
#######################################

def signal_handler(signal, frame):
    """Method to handle a signal"""
    if debug: log("Caught a signal %s"%(signal))
    # If our original event type was a startup, naturally we would now be shutting down.
    if eventType == "startup":
        do_system_event("shutdown")
    # Likewise for a login event
    elif eventType == "login":
        do_system_event("logout")



#######################################
# Code to handle the passed argument (event type)
#######################################

argc = len(sys.argv)
if argc < 2:
    print 'usage:', os.path.basename(__file__), """[event type]
    
    Available event types:  login, or startup"""
    sys.exit(1)
    
eventType = sys.argv[1]

if eventType in ['login', 'startup']:
    do_system_event(eventType)
else:
    print "Unknown event type: ", eventType



#######################################
# Code that handles catching the unix signal(s)
#######################################

signal.signal(signal.SIGINT, signal_handler)    # SIGINT for command line compatibility (CTRL+C)
signal.signal(signal.SIGTERM, signal_handler)   # SIGTERM will come from launchd on logout or shutdown

# Flush output, otherwise the system.log entries for the startup/login record won't output until the script exits at shutdown/logout
sys.stdout.flush()

signal.pause()                                  # Wait for a signal indefinitely
    
