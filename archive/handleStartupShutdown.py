#!/usr/bin/env python

# serviceManagerMacStartup.py - Handle Startup and Shutdown events for the OAL Login Database
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
call(['rm','/tmp/didshutdown'])

# Script first runs at startup as a LaunchDaemon.
# Therefore, assume a script launch means a startup event.
# Handle that startup event by calling our service manager client with a "startup" event type
try:
    result = call([cwd+'/serviceManagerClient.py', 'startup'])
    assert result == 0, "Non-zero returncode from servicemanager client when sending startup event"
    print "Script started up, sent startup event"
except Exception, e:
    raise e
    
# Script will now wait until a SIGTERM from launchd, which is assumed to mean a shutdown event

# Method to handle the SIGTERM
def signal_handler(signal, frame):
    """Method to handle a signal"""
    # Handle that shutdown event by calling our service manager client with a "shutdown" event type
    try:
        #result = call([cwd+'/serviceManagerClient.py', 'shutdown'])
        #assert result == 0, "Non-zero returncode from servicemanager client when sending shutdown event"
        print "Received a signal %s, sending shutdown record" % (signal)
        call(['touch','/tmp/didshutdown'])
    except Exception, e:
        raise e
    else:
        sys.exit(0)

with NSDisabledSuddenTermination:
    # Define which signals we're interested in
    signal.signal(signal.SIGINT, signal_handler)    # SIGINT for command-line compatibility
    signal.signal(signal.SIGTERM, signal_handler)   # SIGTERM will come from launchd on shutdown
    
    # Flush output, otherwise the log entry for the startup/login record won't output until the script exits at shutdown/logout
    sys.stdout.flush()
    
    # Wait for a signal
    signal.pause()
