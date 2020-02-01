#!/usr/bin/env python

import sys, os
import httplib                      # to connect to our http SOAP service
from xml.dom import minidom         # to be able to read the service's response
from xml.sax.saxutils import escape # to properly escape our XML values
from subprocess import call, Popen, PIPE, STDOUT         # for the ability to use cmdline utilities to obtain system information
import commands 
import re
from time import sleep

# XML Template for the body of our SOAP request. Each %s should be replaced with the appropriate values before sending.
loginRequestTemplate = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <UpdateDatabaseWithLoginLogoutDataMac xmlns="http://oalinfo.tamu.edu/tools/ServiceManager/">
      <Key>thisisakeyforthemacs</Key>
      <UserName>%(username)s</UserName>
      <IPAddress>%(ipAddress)s</IPAddress>
      <ComputerName>%(computerName)s</ComputerName>
      <LogonServer>%(logonServer)s</LogonServer>
      <LoginORLogout>%(loginOrLogout)s</LoginORLogout>
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
      <StartupOrShutdown>%(startupOrShutdown)s</StartupOrShutdown>
    </UpdateDatabaseWithStartupShutdownMac>
  </soap:Body>
</soap:Envelope>"""


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
            print "No active network addresses. Waiting 10 seconds before trying again (elapsed time=%s)" % (self.networkWaitTime)
            if self.networkWaitTime < 30:
                sleep(10)
                self.networkWaitTime += 10
                self.update()
            else:
                print "No active network address ever found. Sending empty IP data, and en0 mac address"
                self.ipAddress = ""
                self.macAddress = commands.getstatusoutput("ifconfig en0 | grep 'ether' | awk {'print $2'}")[1]
        else:
            self.ipAddress = commands.getstatusoutput("ifconfig %s | grep 'inet ' | awk {'print $2'}" % (primaryInt))[1]
            self.macAddress = commands.getstatusoutput("ifconfig %s | grep 'ether' | awk {'print $2'}" % (primaryInt))[1]
       

def do_soap_operation(headers, request, requestMap):
    
    # Merge our keys into the request template
    request = request % requestMap
    
    # Open connection to the service
    connection = httplib.HTTPConnection("oalinfo.tamu.edu", 80)
    
    # Send our request, complete with the headers and body, and save the response
    # connection.request("POST", "/tools/servicemanager/servicemanager.asmx", request, headers)
    #     response = connection.getresponse()
    #     
    #     document = minidom.parseString(response.read())
    #     if response.status != 200:
    #         print "Error code from the service manager: %d" % (response.status)
        
        
        

def do_system_event(eventType):
    """Obtains the system data values and places them into the SOAP request template"""
    
    # Instantiate a SystemInfo object that will have all the system attributes we need
    sysinfo = SystemInfo()
    
    if eventType in ['login', 'logout']:
        requestMap = {
            'username':escape(sysinfo.username),
            'computerName':escape(sysinfo.computerName),
            'ipAddress':escape(sysinfo.ipAddress),
            'logonServer':escape("")
        }
        # LoginOrLogout key: True for a login event, false for a logout event
        requestMap['loginOrLogout'] = "true" if eventType == 'login' else "false"
        headers = {
            'Host':'oalinfo.tamu.edu',
            'Content-Type':'text/xml; charset=utf-8',
            'SOAPAction':"http://oalinfo.tamu.edu/tools/ServiceManager/UpdateDatabaseWithLoginLogoutDataMac"
        }
        do_soap_operation(headers, loginRequestTemplate, requestMap)
        
    elif eventType in ['startup', 'shutdown']:
        requestMap = {
            'computerName':escape(sysinfo.computerName),
            'ipAddress':escape(sysinfo.ipAddress)
        }
        # StartupOrShutdown key: True for a startup event, false for a shutdown event
        requestMap['startupOrShutdown'] = "true" if eventType == 'startup' else "false"
        headers = {
            'Host':'oalinfo.tamu.edu',
            'Content-Type':'text/xml; charset=utf-8',
            'SOAPAction':"http://oalinfo.tamu.edu/tools/ServiceManager/UpdateDatabaseWithStartupShutdownMac"}
        do_soap_operation(headers, startupRequestTemplate, requestMap)
        
            
argc = len(sys.argv)
if argc < 2:
    print 'usage:', os.path.basename(__file__), """[event type]
    
    Available event types:  login, logout, startup, and shutdown"""
    sys.exit(1)
    
eventType = sys.argv[1]

if eventType in ['login', 'logout', 'startup', 'shutdown']:
    do_system_event(eventType)
else:
    print "Unknown event type: ", eventType
