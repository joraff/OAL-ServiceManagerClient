#!/usr/bin/env python

# Signal trap experiments

import signal, time
import sys
from subprocess import call

class Session(object):
    """docstring for Session"""
    def __init__(self, arg):
        super(Session, self).__init__()
        self.arg = arg
        

def log(s):
    localtime = time.asctime( time.localtime(time.time()) )
    print s
    with open("/var/log/pytest.log", "a") as f:
         f.write(localtime+": "+s+"\n")

def write_session(object):
    """docstring for write_session"""
    pass
log("Signal experiment program is running...")

def signal_handler(signal, frame):
    """method to handle a signal"""
    log("Caught a %s signal" % (signal))
    
    
signal.signal(signal.SIGHUP, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

signal.pause()