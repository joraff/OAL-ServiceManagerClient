#!/usr/bin/env python

import sys, os
import httplib                      # to connect to our http SOAP service
from xml.dom import minidom         # to be able to read the service's response
from xml.sax.saxutils import escape # to properly escape our XML values
from subprocess import call         # for the ability to use cmdline utilities to obtain system information
import commands 
import re


def do_soap_operation(headers, request):
    
    print request
    
    # Open connection to the service
    connection = httplib.HTTPConnection("oalinfo.tamu.edu", 80)
    connection.set_debuglevel(1)
    
    # Send our request, complete with the headers and body, and save the response
    connection.request("POST", "/tools/servicemanager1/servicemanager.asmx", request, headers)
    response = connection.getresponse()

    data = response.read()
    print data
    document = minidom.parseString(data)
    print response.msg
    if response.status == 500:
        return document.getElementsByTagName("faultstring")
    else:
        return document.getElementsByTagName("URL")
        
        
# XML Template for the body of our SOAP request. Each %s should be replaced with the appropriate values before sending.
request = """<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <UpdateDatabaseWithLoginLogoutDataMac xmlns="http://oalinfo.tamu.edu/tools/ServiceManager/">
            <Key>thisisakeyforthemacs</Key>
            <UserName>test</UserName>
            <IPAddress>123.123.123.123</IPAddress>
            <ComputerName>test-computer</ComputerName>
            <LoginORLogout>true</LoginORLogout>
            <UpdateTime>2011-12-09T10:37:00</UpdateTime>
        </UpdateDatabaseWithLoginLogoutDataMac>
    </soap:Body>
</soap:Envelope>"""

request = request.replace("\n", "\r\n")

headers = {
    'Host':'oalinfo.tamu.edu',
    'Content-Type':'text/xml; charset=utf-8',
    'SOAPAction':"\"http://oalinfo.tamu.edu/tools/ServiceManager/UpdateDatabaseWithLoginLogoutDataMac\""
}

do_soap_operation(headers, request)

