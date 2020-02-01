#!/usr/bin/env python


# service_manager.py
# Copyright 2011 Texas A&M University
# Joseph Rafferty
# jrafferty@tamu.edu
# 
# Script that is started at boot and handles sending all session events to the OAL service manager for Mac computers.
# It understands and handles startup, shutdown, login, and logout events.
# In the event that the network is not available when trying to send an event, 
#     it writes the event data to disk and will try to handle it next time the script runs.



import sys, os
import httplib                      # to connect to our http SOAP service
from xml.dom import minidom         # to be able to read the service's response
from xml.sax.saxutils import escape # to properly escape our XML values
from subprocess import call, Popen, PIPE, STDOUT         # for the ability to use cmdline utilities to obtain system information
import signal
import commands
import re
import time
from datetime import datetime
import pickle


#######################################
# Logging stuff.
#######################################

# Change your log level here.
log_levels = ["error", "info", "debug"]
log_level = "info"

def log(s, level):
    if (log_levels.index(level) <= log_levels.index(log_level)):
        localtime = time.asctime( time.localtime(time.time()) )
        print s
        with open("/Library/Logs/OAL Service Manager.log", "a") as f:
            f.write(localtime+": "+s+"\n")
            
            
class SystemInfo:
    networkWaitTime = 0

    def __init__(self):
        """Init our object with the system information attributes we need"""
        self.update()

    def update(self):
        """Update ourselves with the latest system information"""
        # Use scutil (System Configuration Utility) to query configd for our ComputerName
        self.computerName = commands.getstatusoutput("scutil --get ComputerName")[1]
        
        # Get the console user
        # self.username = commands.getstatusoutput("stat -f%Su /dev/console")[1]
        # Strip any realm that might go along with it
        # self.username = re.search("([^@]*)", self.username).group(1) 

        # Obtain the primary interface by grabbing the first en(i) device listed in the service order.
        try:
            p = Popen(['scutil'], stdout=PIPE, stdin=PIPE, stderr=STDOUT)
            stdout = p.communicate(input='open\nget State:/Network/Global/IPv4\nd.show\nquit\n')[0]
            primaryInt = re.search("PrimaryInterface : (.*)", stdout).group(1)
        except AttributeError, e:
            log("No active network addresses. Waiting 10 seconds before trying again (elapsed time=%s)" % ( self.networkWaitTime), "debug")
            if self.networkWaitTime < 20:
                time.sleep(10)
                self.networkWaitTime += 10
                self.update()
            else:
                log("No active network interface ever found. Sending empty IP data, and en0 mac address", "debug")
                self.ipAddress = ""
                self.macAddress = commands.getstatusoutput("ifconfig en0 | grep 'ether' | awk {'print $2'}")[1]
        else:
            self.ipAddress = commands.getstatusoutput("ifconfig %s | grep 'inet ' | awk {'print $2'}" % (primaryInt))[1]
            self.macAddress = commands.getstatusoutput("ifconfig %s | grep 'ether' | awk {'print $2'}" % (primaryInt))[1]
    
    
    def network_up(self):
        """Check for network up status"""
        try:
            p = Popen(['scutil'], stdout=PIPE, stdin=PIPE, stderr=STDOUT)
            stdout = p.communicate(input='open\nget State:/Network/Global/IPv4\nd.show\nquit\n')[0]
            primaryInt = re.search("PrimaryInterface : (.*)", stdout).group(1)
        except AttributeError, e:
            return False
        else:
            return True
            
    def username(self):
        uname = commands.getstatusoutput("stat -f%Su /dev/console")[1]
        uname = re.search("([^@]*)", uname).group(1)
        return uname
        
sysInfo = SystemInfo()





#######################################
# XMLRPC templates.
#######################################

loginRequestTemplate = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <UpdateDatabaseWithLoginLogoutDataMac xmlns="http://server/tools/ServiceManager/">
      <Key>supersecretkey</Key>
      <UserName>%(username)s</UserName>
      <ComputerName>%(computerName)s</ComputerName>
      <IPAddress>%(ipAddress)s</IPAddress>
      <MACAddress>%(macAddress)s</MACAddress>
      <LoginORLogout>%(loginOrLogout)s</LoginORLogout>
      <UpdateTime>%(eventTime)s</UpdateTime>
    </UpdateDatabaseWithLoginLogoutDataMac>
  </soap:Body>
</soap:Envelope>"""

startupRequestTemplate = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
  <soap:Body>
    <UpdateDatabaseWithStartupShutdownMac xmlns="http://server/tools/ServiceManager/">
      <Key>supersecretkey</Key>
      <ComputerName>%(computerName)s</ComputerName>
      <IPAddress>%(ipAddress)s</IPAddress>
      <MACAddress>%(macAddress)s</MACAddress>
      <StartupOrShutdown>%(startupOrShutdown)s</StartupOrShutdown>
      <UpdateTime>%(eventTime)s</UpdateTime>
    </UpdateDatabaseWithStartupShutdownMac>
  </soap:Body>
</soap:Envelope>"""


#######################################
# Session is our parent class. It isn't intended to be instantiated directly.
# It contains most of the shared methods and attributes for our different session types
# Subclass this class for your other session types
#######################################

class Session(object):
    path = "oalsm-default.pid"
    sessionTypeName = "session"
    
    def __init__(self):
        log("%s object init" % self.sessionTypeName, "debug")
        self.eventTime = datetime.now()
        self.requestMap = {}
        self.requestTemplate = None
        self.headers = None
    
    
    #######################################
    # update(): changes the last updated time to the current time, and writes the session to its output file
    #######################################
    
    def update(self):
        self.eventTime = datetime.now()
        self.save()
        log("Updated %s event time to %s" % (self.sessionTypeName, self.eventTime), "debug")
    
    
    #######################################
    # do_soap_operation(): creates the request, opens the connection, and sends our SOAP request
    #######################################
    
    def do_soap_operation(self, headers, request, requestMap):
        # Merge our keys into the request template
        request = request % requestMap
        log("soap: mapped request", "debug")
        # Open connection to the service
        connection = httplib.HTTPConnection("server", 80)
        log("soap: opened connection", "debug")
        # Send our request, complete with the headers and body, and save the response
        connection.request("POST", "/tools/servicemanager/servicemanager.asmx", request, headers)
        log("soap: sent request", "debug")
        response = connection.getresponse()
        log("soap: got response", "debug")
        document = minidom.parseString(response.read())
        if response.status != 200:
            log("soap: Error code from the service manager: %d" % (response.status), "debug")
            if response.status == 500 and debug:
                log("soap: Detailed error message: %s" % document.getElementsByTagName("faultstring"), "debug")
            return False
        else:
            log("soap: 200 OK response", "debug")
            return True


    #######################################
    # send(): adds generic session attribute data, and calls the soap method
    #######################################

    def send(self):
        """Obtains the system data values and places them into the SOAP request template"""
        self.requestMap.update({ 'computerName':escape(sysInfo.computerName),
                                 'ipAddress':escape(sysInfo.ipAddress),
                                 'macAddress':escape(sysInfo.macAddress),
                                 'eventTime':escape(self.eventTime.strftime("%Y-%m-%dT%H:%M:%S")) })        
        log("%s" % self.requestMap, "debug")
        if sysInfo.network_up():
            self.do_soap_operation(self.headers, self.requestTemplate, self.requestMap)
            log("Truncating file: %s" % self.path, "debug")
            file(self.path, 'w+b')
        else:
            log("Network is down, saving %s to disk instead" % self.sessionTypeName, "debug")
            self.update()
    
    
    
    #######################################
    # save(): serializes itself and writes it to a file
    #######################################

    def save(self):
        log("Saving %s session to file: %s" % (self.sessionTypeName, self.path), "debug")
        pickle.dump( self, open( self.path, "wb" ) )

    @classmethod
    def load(cls):
        log("Loading %s session from file: %s" % (cls.sessionTypeName, cls.path), "debug")
        return pickle.load( open( cls.path, "rb" ) )

    @classmethod
    def check_previous(cls):
        log("Checking for %s session at file: %s" % (cls.sessionTypeName, cls.path), "debug")
        try:
            if(os.stat(cls.path).st_size):
                log("%s session found. Loading and sending" % cls.sessionTypeName, "debug")
                s = cls.load()
                s.send()
            else:
                log("No %s session found at %s" % (cls.sessionTypeName, cls.path), "debug")
        except (OSError):
            log("No session file found at %s" % (cls.path), "debug")

#######################################
# The Login class
#######################################

class Login (Session):
    loginOrLogout = "true"      # XMLRPC key, true for login, false for logout
    sessionTypeName = "login"   # for better log data
    path = "oalsm-login.pid"
    
    #######################################
    # __init__(): adds the username attribute during initialization, so it gets saved to disk
    #######################################
    
    def __init__(self):
        super(Login, self).__init__()
        self.username = sysInfo.username()
    
    
    #######################################
    # send(): adds the login-specific attributes to the XML request
    #######################################
    
    def send(self):
        log("Sending a %s event for: %s" % (self.sessionTypeName,self.username), "info")
        self.requestMap['loginOrLogout'] = self.loginOrLogout
        self.requestMap['username'] = self.username
        self.requestTemplate = loginRequestTemplate
        self.headers  = { 'Host':'server',
                          'Content-Type':'text/xml; charset=utf-8',
                          'SOAPAction':"http://server/tools/ServiceManager/UpdateDatabaseWithLoginLogoutDataMac" }
        return super(Login, self).send()

class Logout (Login):
    loginOrLogout = "false"
    sessionTypeName = "logout"
    path = "oalsm-logout.pid"
    def __init__(self):
        super(Logout, self).__init__()
        #self.save()
        
    
class Startup (Session):
    startupOrShutdown = "true"
    sessionTypeName = "startup"
    path = "oalsm-startup.pid"
    
    def send(self):
        log("Sending a %s event" % self.sessionTypeName, "info")
        self.requestMap['startupOrShutdown'] = self.startupOrShutdown
        self.requestTemplate = startupRequestTemplate
        self.headers = { 'Host':'server',
                         'Content-Type':'text/xml; charset=utf-8',
                         'SOAPAction':"http://server/tools/ServiceManager/UpdateDatabaseWithStartupShutdownMac" }
        return super(Startup, self).send()


class Shutdown (Startup):
    startupOrShutdown = "false"
    sessionTypeName = "shutdown"
    path = "oalsm-shutdown.pid"
    def __init__(self):
        super(Shutdown, self).__init__()
        #self.save()



# Check for leftover sessions
Startup.check_previous()
Login.check_previous()
Logout.check_previous()
Shutdown.check_previous()


Startup().send()
pendingShutdown = Shutdown()
pendingShutdown.save()
pendingLogout = None



# Setup our signal traps and handler. This enables us to try and send off the closing requests if there's a network connection.
#  If there's no connection, the request will simply time out and the session output files will be parsed next time the script runs.
def signal_handler(signal, frame):
    """docstring for signal_handler"""
    if pendingLogout: pendingLogout.send()
    pendingShutdown.send()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler) 
signal.signal(signal.SIGTERM, signal_handler) 

# Always instantiate as the root (loginwindow) user. We don't want to detect the console user here, because what if
#  a user logs on before this script runs? Its unlikely, but if true we would miss that login event.
#  Also, we do not enable the root user for login, therefore root will never be logged in at the console
previousUser = "root"


while(True):
    # Check who our console user is for this loop.
    newUser = commands.getstatusoutput("stat -f%Su /dev/console")[1]
    newUser = re.search("([^@]*)", newUser).group(1)
    
    # If the user changed, we have work to do!
    if newUser != previousUser:
        log("Different username detected. New- %s, Old-%s" % (newUser, previousUser), "debug")
        if newUser == "root":
            # LOGOUT
            log("New user is root - we had a logout. Sending logout for session: %s" % pendingLogout.username, "debug")
            pendingLogout.send()
            pendingLogout = None
        elif previousUser == "root":
            # LOGIN
            log("New user is %s - we had a login. Sending login for new session: %s" % (newUser, newUser), "debug")
            Login().send()
            pendingLogout = Logout()
            pendingLogout.save()
        else:
            # LOGOUT AND LOGIN
            log("Neither username was root, indicating we had both a logout/login during our sleep period.")
            log("Sending logout for session: %s" % pendingLogout.username, "debug")
            log("Sending login for new session: %s" % newUser, "debug")
            pendingLogout.handle_event()
            Login().send()
            pendingLogout = Logout()
            pendingLogout.save()
    else:
        log("No username difference", "debug")
    
    previousUser = newUser
    
    # Update our timestamps for the current sessions
    if pendingLogout:
        pendingLogout.update()
    pendingShutdown.update()
    
    time.sleep(5)