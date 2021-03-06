#!/usr/bin/env python

# Signal trap experiments

import signal, time
import sys
from subprocess import call#!/usr/bin/env python

# serviceManagerMacStartup.py - Handle Startup and Shutdown events for the OAL Login Database
# 
# Part of the OAL ServiceManager suite of scripts for Macs
# 
# Copyright 2011 Texas A&M University
# Joseph Rafferty
# CIS Open Access Labs
# jrafferty@tamu.edu

import sys, os, time
import signal
from subprocess import call


# Base path for the service manager client script
cwd = os.path.dirname(__file__)

# Method to handle logging of the service manager calls
def log(s):
    localtime = time.asctime( time.localtime(time.time()) )
    print s
    with open("/Library/Logs/oalsm.log", "a") as f:
         f.write(localtime+": "+s+"\n")


# Script first runs at startup as a LaunchDaemon.
# Therefore, assume a script launch means a startup event.
# Handle that startup event by calling our service manager client with a "startup" event type

def handle_event(eventType):
    log("Handling a %s event"%(eventType))
    try:
        result = call([cwd+'/serviceManagerClient.py', '%s'%(eventType)])
        assert result == 0, "Non-zero returncode from servicemanager client when sending %s event"%(eventType)
        log("Servicemanager client successfully sent %s event"%(eventType))
    except Exception, e:
        raise e
    
# Script will now wait until a SIGTERM from launchd, which is assumed to mean a shutdown event

# Method to handle the SIGTERM
def signal_handler(signal, frame):
    """Method to handle a signal"""
    log("Caught a signal %s"%(signal))
    # If our original event type was a startup, naturally we would now be shutting down.
    if eventType == "startup":
        handle_event("shutdown")
    # Likewise for a login event
    elif eventType == "login":
        handle_event("logout")
        



argc = len(sys.argv)
if argc < 2:
    print 'usage:', os.path.basename(__file__), """[event type]
    
    Available event types:  login or startup"""
    sys.exit(1)
    
eventType = sys.argv[1]

if eventType in ['login', 'startup']:
    handle_event(eventType)
else:
    print "Unknown event type: ", eventType


# Define which signals we're interested in
signal.signal(signal.SIGINT, signal_handler)    # SIGINT for command-line compatibility
signal.signal(signal.SIGTERM, signal_handler)   # SIGTERM will come from launchd on logout/shutdown

# Flush output, otherwise the log entry for the startup/login record won't output until the script exits at shutdown/logout
sys.stdout.flush()

# Wait for a signal
signal.pause()


def log(s):
    localtime = time.asctime( time.localtime(time.time()) )
    print s
    with open("/var/log/pytest.log", "a") as f:
         f.write(localtime+": "+s+"\n")


log("Program is running...")

def signal_handler(signal, frame):
    """method to handle a signal"""
    log("Caught a %s... Shutting down" % (signal))
    sys.exit(0)
    
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

signal.pause()