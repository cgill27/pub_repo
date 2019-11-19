# -*- coding: utf-8 -*-
"""
cc_get_all_campaigns.py

Description:
This script gets a list of all the campaigns at Constant Contact

Last committed: $Date: 2014-10-13 13:54:30 -0500 (Mon, 13 Oct 2014) $
Revision number: $Revision: 42 $
Author: $Author: cgill $
URL: $HeadURL: https://localhost/constant-contact/python/cc_get_all_campaigns.py $

"""
try:
    import pycurl
except ImportError:
    print "Module 'pycurl' not installed!  Exiting script"
    quit(2)
import json
import StringIO
try:
    import argparse
except ImportError:
    print "Module 'argparse' not installed!  Exiting script"
    quit(2)
try:
    from pyfiglet import Figlet
    figlet_installed = True
except ImportError:
    figlet_installed = False
import os
import logging
from datetime import datetime
import time
try:
    import dateutil.parser
except ImportError:
    print "Module 'python-dateutil' not installed!  Exiting script"
    quit(2)
try:
    import pytz
except ImportError:
    print "Module 'pytz' not installed!  Exiting script"
    quit(2)
import sys

# Check Python version and exit if not atleast 2.7
req_version = (2, 7)
cur_version = os.sys.version_info

if not cur_version >= req_version:
    print "Your Python interpreter is too old. Please consider upgrading to atleast 2.7"
    quit(2)

# If False then no logs are created, only the status at the end is displayed
debug = True

# Get name, path, version of this script
script_name = __file__
script_path = os.path.dirname(os.path.abspath(__file__))
script_version = "$Id: cc_get_all_campaigns.py 42 2014-10-13 18:54:30Z cgill $"

# Constant Contact api uri, the rest of the url is completed below for pagination
cc_api_url = 'https://api.constantcontact.com'

# Constant Contact api key
api_key = ""

# Constant Contact access token
access_token = ""

got_error = False  # If not changed to True then script ran with 0 errors
campaign_count = 0  # Track number of new campaigns found since last run

# Set local time zone for converting time
local_tz = pytz.timezone('America/Chicago')


def printhelp():
    # Show help options
    if figlet_installed is True:
        f = Figlet(font='slant')
        print f.renderText(script_name)
    print " "
    print "This script gets a list of all the campaigns at Constant Contact"
    print " "
    print "Usage: %s" % script_name
    print " "
    print "Optional args:"
    print "-d | --debuglevel    Level of logging (debug, info, warning, error, critical)"
    print "-l | --debuglog      Log file to log to (full path)"
    print "-v | --version       Show script version info"
    print "Note: if 'TIMESTAMP' is in debugLog file name, it will be substituted with a timestamp"
    print "Note2: 'debug = True' must be set in script for logging to happen"
    print " "
    print "Help: %s -h" % script_name
    print " "
    quit(1)

# Parse cli options
parser = argparse.ArgumentParser(description="Script gets a list of all the campaigns at Constant Contact")
# Optional args
parser.add_argument("-d", "--debugLevel", type=str, choices=["debug", "info", "warning", "error", "critical"], help="Set debug level")
parser.add_argument("-l", "--debugLog", type=str, help="Debug log file name if debugLevel is set")
parser.add_argument("-v", "--version", action="version", version="$Id: cc_get_all_campaigns.py 42 2014-10-13 18:54:30Z cgill $")
# Check for help argument and print help
if "-h" in sys.argv or "--help" in sys.argv:
    printhelp()
args = parser.parse_args()

# Setup logging if specified at cli
if args.debugLevel:
    debugLevel = args.debugLevel
    debugLevel = debugLevel.strip()
    if args.debugLog:
        debugLog = args.debugLog
        debugLog = str(debugLog)
        debugLog = debugLog.strip()
        if debugLog.find("TIMESTAMP") > 0:  # If the word 'TIMESTAMP' is found in debugLog, replace with debugLog_suffix
            # https://docs.python.org/2/library/time.html
            debugLog_suffix = datetime.now().strftime("%Y%m%d%H%M%S")  # 20130101235959  year month day hour minute second
            debugLog = debugLog.replace("TIMESTAMP", debugLog_suffix)
        debugLogDir = os.path.dirname(os.path.abspath(debugLog))
        if not os.path.isdir(debugLogDir):
            print "Option 'debugLog' needs to specify full path to a log file!  Exiting script"
            printhelp()
    else:
        print "If specifying debugLevel, also specify debugLog!  Exiting script"
        printhelp()
    debugLevelOptions = ["debug", "info", "warning", "error", "critical"]
    if debugLevel in debugLevelOptions:
        if debugLevel == "debug":
            logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog, filemode='a')
        elif debugLevel == "info":
            logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog, filemode='a')
        elif debugLevel == "warning":
            logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog, filemode='a')
        elif debugLevel == "error":
            logging.basicConfig(level=logging.ERROR, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog, filemode='a')
        elif debugLevel == "critical":
            logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog, filemode='a')
    else:
        print "Option 'debugLevel' needs to be one of [debug, info, warning, error, critical]!  Exiting script"
        printhelp()
    loggingEnabled = True
else:
    loggingEnabled = False
    debugLevel = ""
    debugLog = ""


def logger(log, level="debug"):
    """ Log to debugLog if logging enabled """
    if loggingEnabled and debug:  # Only log if debugging set to True (top of this script) and debug level/log are set at the cli
        if level == "debug":
            logging.debug(log)
        if level == "info":
            logging.info(log)
        if level == "warning":
            logging.warning(log)
        if level == "error":
            logging.error(log)
        if level == "critical":
            logging.critical(log)
        return True
    else:
        return False

# Start the log file if logging specified
logger(" ", "info")
logger("--+** Starting '%s' script **+--" % script_name, "info")
script_start_time = time.time()
logger("script_path = '%s'" % script_path, "debug")
logger("script_version = '%s'" % script_version, "debug")
if debugLevel is not "":
    logger("debugLevel = '%s'" % debugLevel, "debug")
if debugLog is not "":
    logger("debugLog = '%s'" % debugLog, "debug")
logger("Constant Contact api key = '%s'" % api_key, "debug")
logger("Constant Contact access token = '%s'" % access_token, "debug")

# HTTP headers, include access token and json content type
http_header = ["Authorization: Bearer " + access_token, "Content-Type: application/json"]


def get_all_campaigns(api_url):
    """ Perform curl to get a list of all the unsubs for a campaign id
        return dictionary of (campaign_id: campaign_name)
    """
    c = pycurl.Curl()  # Perform curl
    response_content = StringIO.StringIO()
    c.setopt(pycurl.URL, api_url)
    logger("api_url = %s" % api_url)
    c.setopt(pycurl.HTTPHEADER, http_header)
    c.setopt(pycurl.WRITEFUNCTION, response_content.write)
    c.setopt(c.CONNECTTIMEOUT, 15)
    c.setopt(c.TIMEOUT, 20)
    try:
        logger("Performing pycurl get for all campaigns...", "debug")
        c.perform()
    except pycurl.error, error:
        errno, errstr = error
        logger("Pycurl error code: %s  error: %s" % (errno, errstr), "critical")
        print "Pycurl error code: %s  error: %s" % (errno, errstr)

    # Constant Contact response codes:
    # http://developer.constantcontact.com/docs/email-campaigns/email-campaigns-collection.html?method=GET
    # 200 - Request was successful
    # 401 - Authentication failure
    # 404 - Email campaign(s) not found
    # 406 - Unsupported Accept Header value, must be application/json
    # 500 - Internal server error occurred

    # Get integer response code and close curl handle
    response_code = c.getinfo(c.RESPONSE_CODE)
    logger("Pycurl response code: %s" % response_code, "debug")
    if response_code == 200:  # If request successful return json decoded dictionary of results
        response_object = json.loads(response_content.getvalue())  # On success returns a list containing dictionary objects
        c.close()
        return response_object
    elif response_code == 401:
        c.close()
        logger("Authentication failed!", "debug")
        return False
    else:  # Request failed
        c.close()
        logger("Request Failed!  Response code: %s  Response error: %s" % (response_code, str(response_content.getvalue())), "critical")
        return False

dict_items = {}  # Dictionary to store all campaign info, key is campaign id

# Get initial set of campaign info, there is a hard limit of 50 results for each api call
cc_api_initial_url = cc_api_url + "/v2/emailmarketing/campaigns"
initial_unsubs = get_all_campaigns(cc_api_initial_url + "?api_key=" + api_key)
if initial_unsubs is False:  # Something went wrong in api call
    print "Request for initial campaign info failed!  See debug log"
    quit(2)

# Put campaign info into dictionary with campaign id as key and campaign details dictionary as value
pagination_required = False
for k, v in initial_unsubs.iteritems():
    if k == "meta":
        # Example: next_link = "/v2/emailmarketing/campaigns?next=MDAwMDA"
        try:
            cc_api_next_url = v['pagination']['next_link']
            pagination_required = True
        except KeyError:  # 'next_link' not found
            pagination_required = False
    else:
        for x in v:
            dict_items[x['id']] = x

# Clear previously used vars
k = None
v = None
x = None

# Pagination is required so loop over pages to get all campaign's
if pagination_required is True:
    next_link = True
    while next_link is True:  # Loop through api calls until no more pagination results found
        unsubs_next = get_all_campaigns(cc_api_url + cc_api_next_url + "&api_key=" + api_key)
        if unsubs_next is False:  # Something went wrong in api call
            print "Request for next link failed!  See debug log"
            quit(2)
        found_nextlink = False
        for k, v in unsubs_next.iteritems():
            if k == "meta":
                # Example: next_link = "/v2/emailmarketing/campaigns?next=MDAwMDA"
                try:
                    cc_api_next_url = v['pagination']['next_link']
                    found_nextlink = True
                except KeyError:  # 'next_link' not found so end of the list
                    found_nextlink = False
            else:
                for x in v:
                    dict_items[x['id']] = x
        if found_nextlink is True:
            next_link = True
        else:
            next_link = False

# Clear previously used vars
k = None
v = None
x = None

delimiter = "|"  # Delimiter to use in output csv results
print "id" + delimiter + "status" + delimiter + "name" + delimiter + "modified_date"
for k, v in dict_items.iteritems():
    # Convert ISO-8601 time to CST
    cst_modified_date = dateutil.parser.parse(v['modified_date'])  # Constant Contact uses ISO-8601 time
    cst_modified_date = cst_modified_date.astimezone(local_tz)
    cst_modified_date = cst_modified_date.strftime("%Y-%m-%d %H:%M:%S")
    print v['id'] + delimiter + v['status'] + delimiter + v['name'] + delimiter + cst_modified_date
