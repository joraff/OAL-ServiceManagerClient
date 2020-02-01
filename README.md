Script that is started at boot and handles sending all session events to the OAL service manager for Mac computers.
- It understands and handles startup, shutdown, login, and logout events.
- In the event that the network is not available when trying to send an event, it writes the event data to disk and will try to handle it next time the script runs.