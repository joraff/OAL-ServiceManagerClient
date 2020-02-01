#!/usr/bin/env bash

# Ensure the log file exists
touch "/Library/Logs/OAL Service Manager.log"

# Ensure non-admin users cannot read or modify the file
chown root:wheel "/Library/Logs/OAL Service Manager.log"
chmod 750 "/Library/Logs/OAL Service Manager.log"
