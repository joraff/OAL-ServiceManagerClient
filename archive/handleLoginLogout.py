#!/usr/bin/env python

# handleStartupShutdown.py - Handle Startup and Shutdown events for the OAL Login Database
# 
# Part of the OAL ServiceManager suite of scripts for Macs
# 
# Copyright 2011 Texas A&M University
# Joseph Rafferty
# CIS Open Access Labs
# jrafferty@tamu.edu

import sys, os
import signal
from subprocess import call
from Foundation import NSDisabledSuddenTermination
import objc

# Base path for the service manager client script
cwd = os.path.dirname(__file__)

# Script first runs at user login as a LaunchAgent.
# Therefore, assume a script launch means a login event.
# Handle that login event by calling our service manager client with a "login" event type
try:
    print "Script launched, sending login record"
    call([cwd+'/serviceManagerClient.py', 'login'])
except Exception, e:
    raise e
    
# Script will now wait until a SIGTERM from launchd, which is assumed to mean a logout event

# Method to handle the SIGTERM
def signal_handler(signal, frame):
    """Method to handle a signal"""
    # Handle that shutdown event by calling our service manager client with a "logout" event type
    try:
        print "Received a %s signal, sending logout record" % (signal)
        call([cwd+'/serviceManagerClient.py', 'logout'])
    except Exception, e:
        raise e
    else:
        sys.exit(0)

with NSDisabledSuddenTermination:
    # Define which signals we're interested in
    signal.signal(signal.SIGINT, signal_handler)    # SIGINT for command-line compatibility
    signal.signal(signal.SIGTERM, signal_handler)   # SIGTERM will come from launchd
    
    # Flush output, otherwise the log entry for the startup/login record won't output until the script exits at shutdown/logout
    sys.stdout.flush()
    
    # Wait for a signal
    signal.pause()
