# -*- coding: utf-8 -*-
"""
check_syspro_invoice_client.py

Description:
This script scans recent xml files created by RAPI for the
 invoice number of an order and checks that the order was
 imported into Syspro and alerts if it wasn't

Last committed: $Date: 2014-10-23 17:44:34 -0500 (Thu, 23 Oct 2014) $
Revision number: $Revision: 275 $
Author: $Author: $
URL: $HeadURL: https://host/repo/check_syspro_invoice/check_syspro_invoice_client.py $

"""
import os
import time
import logging
import argparse
from datetime import datetime
import sys
import json
import StringIO

try:
    from lxml import etree
except ImportError:
    print "No lxml module installed!  Exiting"
    quit(2)
try:
    import pycurl
except ImportError:
    print "No pycurl module installed!  Exiting"
    quit(2)

# Get name of this script
script_name = __file__

# Api key for listener
api_key = ""

# URL to post to for api call
api_url = "https://localhost:8000/"

# Default status of API call, set to True when successful, default False
api_status = False

# Track API call failure count
api_failure_count = 0


def printhelp():
    print " "
    print "This script scans recent xml files created by RAPI for the"
    print " invoice number of an order and checks that the order was"
    print " imported into Syspro and alerts if it wasn't"
    print " "
    print "Usage: %s -f /full/path/to/rapi/outgoing" % script_name
    print "Optional: %s -f /full/path/to/rapi/outgoing -d debug -l xyz123.xml -p"
    print " "
    print "Options:"
    print "   -d | --debuglevel       Set debug level"
    print "   -f | --filedir          Source directory where xml, indexfile, and error logs reside"
    print "   -l | --lastfilechecked  Use this file as the last file checked and check only newer ones"
    print "   -p | --ping             Perform ping to api listener first before running and only run if ping successful"
    print "   -v | --version          Display version of this script"
    print " "
    print "Help: %s -h" % script_name
    print " "
    quit(1)

# Parse cli options
parser = argparse.ArgumentParser(description="Script to check if PO number from RAPI xml files are in the Syspro database")
parser.add_argument("-d", "--debuglevel", type=str, choices=["debug", "info", "warning", "error", "critical"], help="Set debug level (default to 'critical')")
parser.add_argument("-f", "--filedir", type=str, help="Source directory where xml, indexfile, and error logs reside")
parser.add_argument("-l", "--lastfilechecked", type=str, help="Use this file as the last file checked and check only newer ones")
parser.add_argument("-p", "--ping", help="Perform ping to api listener first before running and only run if ping successful", action='store_true')
parser.add_argument("-v", "--version", action="version", version="$Id: check_syspro_invoice_client.py 275 2014-10-23 22:44:34Z $")
# Check for help argument and print help
if "-h" in sys.argv or "--help" in sys.argv:
    printhelp()
# Print help if we don't have all the required args
if len(sys.argv) < 2:
    printhelp()
args = parser.parse_args()

# Source directory where all xml, indexfile, and error logs will reside
if args.filedir and os.path.isdir(args.filedir):
    fileDir = args.filedir
    fileDir = fileDir.strip()
    # Strip the trailing / if its present
    if fileDir.endswith("/"):
        fileDir = fileDir.rstrip("/")
else:
    # cli filedir not provided so use my testing directory
    fileDir = "/home/name/t/outgoing"
    if not os.path.isdir(fileDir):
        print "No 'fileDir' specified and testing directory does not exist!  Exiting script"
        quit(2)

indexFile = fileDir + "/" + "indexfile.dat"  # File containing last checked o.xml file
errorLogFilename = fileDir + "/" + "po_not_found.log"  # Log of invoices/customers not found
debugLog = fileDir + "/" + "check_po_syspro.log"  # Debug log of script execution

# Setup logging
if args.debuglevel:
    if args.debuglevel == "debug":
        logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog, filemode='a')
    elif args.debuglevel == "info":
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog, filemode='a')
    elif args.debuglevel == "warning":
        logging.basicConfig(level=logging.WARNING, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog, filemode='a')
    elif args.debuglevel == "error":
        logging.basicConfig(level=logging.ERROR, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog, filemode='a')
    elif args.debuglevel == "critical":
        logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog, filemode='a')
else:
    logging.basicConfig(level=logging.CRITICAL, format='%(asctime)s %(levelname)s %(message)s', filename=debugLog, filemode='a')

# Make sure fileDir exists before continuing
if not os.path.isdir(fileDir):
    logging.critical("Directory for fileDir %s does not exist!  Exiting" % fileDir)
    quit(2)
else:
    logging.info(" ")
    logging.info("Starting...")
    logging.info("Listener api url: %s" % api_url)
    logging.info("Listener api key: %s" % api_key)

# Report which fileDir we're using
if args.filedir and os.path.isdir(args.filedir):
    logging.debug("Getting fileDir '%s' from cli option filedir" % fileDir)
else:
    # cli filedir not provided so use my testing directory
    logging.debug("Using built-in fileDir '%s' from script" % fileDir)


def pinglistener():
    """ Do ping to listener """
    c = pycurl.Curl()
    response_content = StringIO.StringIO()
    c.setopt(pycurl.URL, api_url)
    # Create json object to send to listener
    data = json.dumps({"api_key": api_key, "operation": "ping"})
    c.setopt(pycurl.POST, 1)
    c.setopt(pycurl.POSTFIELDS, data)
    c.setopt(pycurl.WRITEFUNCTION, response_content.write)
    c.setopt(c.SSL_VERIFYPEER, 0)  # Disable curl verifypeer
    c.setopt(c.SSL_VERIFYHOST, 0)  # Disable curl verifyhost
    c.setopt(c.CONNECTTIMEOUT, 15)
    c.setopt(c.TIMEOUT, 20)
    try:  # Perform curl api call
        c.perform()
    except pycurl.error, cerror:
        errno, errstr = cerror
        logging.critical("Pycurl ping error code: %s  error: %s" % (errno, errstr))
        return False
    response_code = c.getinfo(c.RESPONSE_CODE)
    logging.debug("Pycurl ping response code: %s" % response_code)
    if response_code == 200:  # If request successful return json decoded dictionary of results
        response_object = json.loads(response_content.getvalue())  # On success returns a list containing dictionary objects
        c.close()
        if response_object['ping'] == "successful":
            logging.debug("Listener api ping successful")
            return True
        else:
            return False
    elif response_code == 401:  # Authentication failed, check api key
        c.close()
        logging.critical("Ping API Authentication failed!")
        return False
    else:  # Request failed
        c.close()
        logging.critical("Ping Request Failed!  Response code: %s  Response error: %s" % (response_code, str(response_content.getvalue())))
        return False


# Perform listener api ping to see if api is up before continuing if -p specified
if "-p" in sys.argv or "--ping" in sys.argv or args.ping is True:
    ping_listener = pinglistener()
    if ping_listener is False:
        print "Pinging listener failed!  Exiting script"
        logging.critical("Pinging listener failed!  Exiting script")
        quit(2)

if not args.lastfilechecked:
    # Get last checked o.xml file from the index file
    logging.debug("Opening index file '%s'" % indexFile)
    if os.path.exists(indexFile) and os.path.isfile(indexFile):
        try:
            f = open(indexFile, 'r')
            lastFileModifiedFilename = f.readline()
            lastFileModifiedFilename = lastFileModifiedFilename.strip()
            f.close()
            logging.debug("Found filename %s in index file" % lastFileModifiedFilename)
        except IOError as e:
            logging.critical("Error opening or reading from %s" % indexFile + " - I/O error({0}): {1}".format(e.errno, e.strerror), exc_info=True)
            logging.debug("Exiting script with exit code 2")
            quit(2)
    else:
        logging.critical("Index file %s does not exist!  If first run, create file and insert oldest xml file" % indexFile)
        logging.debug("Exiting script with exit code 2")
        quit(2)
else:
    lastFileModifiedFilename = args.lastfilechecked.lower()
    lastFileModifiedFilename = lastFileModifiedFilename.strip()
    logging.debug("Getting lastFileModifiedFilename '%s' from cli option lastfilechecked" % lastFileModifiedFilename)

# Get file modification time of last checked o.xml file
if lastFileModifiedFilename and len(lastFileModifiedFilename):
    if os.path.exists(fileDir + "/" + lastFileModifiedFilename) and os.path.isfile(fileDir + "/" + lastFileModifiedFilename):
        logging.debug("File %s exists, continuing" % lastFileModifiedFilename)
        lastFileModified = os.stat(os.path.join(fileDir, lastFileModifiedFilename)).st_mtime
        logging.debug("%s last modified: %s" % (lastFileModifiedFilename, datetime.fromtimestamp(lastFileModified)))
    else:
        logging.debug("File %s from %s does not exist" % (lastFileModifiedFilename, indexFile))
        logging.debug("Exiting script with exit code 2")
        quit(2)
else:
    logging.critical("No index filename found in %s!" % indexFile)
    logging.debug("Exiting script with exit code 2")
    quit(2)

# Get a list of all the files in the directory, put them in list, and sort the list
logging.debug("Getting a list of all xml files in the directory and sorting by modified timestamp")
os.chdir(fileDir)
# lst = os.listdir(fileDir)
lst = filter(os.path.isfile, os.listdir(fileDir))  # Make sure only files (not dir's) are in list
# lst = [os.path.join(fileDir, f) for f in lst]  # Add path to each file
lst.sort(key=lambda x: os.path.getmtime(x))  # Sort by modified time

# Create a list of files interated through so we can get the last file
filesCollection = []

# Track if we found any files to check invoice for, default False
filesFound = False


def parsexmlfile(xmlfilefullpath, needle):
    """ Parse XML file """
    try:
        parser = etree.XMLParser(encoding="Windows-1252")
        doc = etree.parse(xmlfilefullpath, parser=parser)
    except etree.XMLSyntaxError as e:
        logging.critical("XML syntax error: " + str(e) + " in file %s" % xmlfilefullpath, exc_info=True)
        # logging.debug("Exiting script with exit code 2")
        # quit(2)
        # Skip this xml file because it can't be parsed
        logging.debug("Unable to parse this xml file, going to skip it and continue to the next xml file if any")
        doc = False
        pass
    except:
        logging.critical("Unable to open xml file: %s" % xmlfilefullpath, exc_info=True)
        logging.debug("Exiting script with exit code 2")
        quit(2)
    if doc is not False:
        root = doc.getroot()
        if root is not False:
            xmlresult = root.xpath(needle)
            if xmlresult is not False:
                # xmlresult = len(xmlresult)
                return xmlresult
            else:
                return False
        else:
            return False
    else:
        return False


def domssqlquery(invoice_num, customer_or_invoice="invoice"):
    """ Do API call to listener """
    c = pycurl.Curl()
    response_content = StringIO.StringIO()
    c.setopt(pycurl.URL, api_url)
    # Create json object to sent to listener
    if customer_or_invoice == "invoice":
        data = json.dumps({"api_key": api_key, "operation": "query", "customer_or_invoice": customer_or_invoice, "invoice": invoice_num})
    elif customer_or_invoice == "customer":
        data = json.dumps({"api_key": api_key, "operation": "query", "customer_or_invoice": customer_or_invoice, "customer": invoice_num})
    else:
        data = json.dumps({"api_key": api_key, "operation": "query", "customer_or_invoice": customer_or_invoice, "invoice": invoice_num})
    c.setopt(pycurl.POST, 1)
    c.setopt(pycurl.POSTFIELDS, data)
    c.setopt(pycurl.WRITEFUNCTION, response_content.write)
    c.setopt(c.SSL_VERIFYPEER, 0)  # Disable curl verifypeer
    c.setopt(c.SSL_VERIFYHOST, 0)  # Disable curl verifyhost
    c.setopt(c.CONNECTTIMEOUT, 15)
    c.setopt(c.TIMEOUT, 20)
    try:  # Perform curl api call
        c.perform()
    except pycurl.error, cerror:
        errno, errstr = cerror
        logging.critical("Pycurl error code: %s  error: %s" % (errno, errstr))
        return False
    response_code = c.getinfo(c.RESPONSE_CODE)
    logging.debug("Pycurl response code: %s" % response_code)
    if response_code == 200:  # If request successful return json decoded dictionary of results
        response_object = json.loads(response_content.getvalue())  # On success returns a list containing dictionary objects
        c.close()
        return response_object
    elif response_code == 401:  # Authentication failed, check api key
        c.close()
        logging.critical("API Authentication failed!")
        return False
    else:  # Request failed
        c.close()
        logging.critical("Request Failed!  Response code: %s  Response error: %s" % (response_code, str(response_content.getvalue())))
        return False


def lognotfoundinsyspro(customerponumber, xmlfile, customerexists=False, customernum=""):
    """ Function to create log file of po's not in Syspro """
    if not customerexists:
        # Customer exists but PO does not exist in Syspro database, log scp command to use
        try:
            x = open(errorLogFilename, 'a')
            timenow = str(datetime.now())
            x.write("-------------\n")
            x.write("%s: 'CustomerPoNumber' %s from file %s not found in Syspro database!\n" % (timenow, customerponumber, xmlfile))
            x.write("%s: Issue the below command as the 'apache' user to re-attempt the import into Syspro:\n" % timenow)
            x.write("%s: scp /home/www/rapi/outgoing/%s sysprossh@aspenacct:/DFMFolder/Comp1/in/AddSalesOrder/%s\n" % (timenow, xmlfile, xmlfile))
            x.close()
        except IOError as e:
            logging.critical("Error opening or writing to %s" % errorLogFilename + " - I/O error({0}): {1}".format(e.errno, e.strerror), exc_info=True)
            logging.debug("Exiting script with exit code 2")
            quit(2)
    else:
        # Customer and PO doesn't exist in Syspro database, log what to do
        try:
            x = open(errorLogFilename, 'a')
            timenow = str(datetime.now())
            x.write("-------------\n")
            x.write("%s: 'Customer' %s and 'CustomerPoNumber' %s from file %s not found in Syspro database!\n" % (timenow, customernum, customerponumber, xmlfile))
            x.write("%s: Need to find out why 'Customer' %s is not imported into Syspro and then you can use the below to re-try po import\n" % (timenow, customernum))
            x.write("%s: Issue the below command as the 'apache' user to re-attempt the po import into Syspro:\n" % timenow)
            x.write("%s: scp /home/www/rapi/outgoing/%s sysprossh@aspenacct:/DFMFolder/Comp1/in/AddSalesOrder/%s\n" % (timenow, xmlfile, xmlfile))
            x.close()
        except IOError as e:
            logging.critical("Error opening or writing to %s" % errorLogFilename + " - I/O error({0}): {1}".format(e.errno, e.strerror), exc_info=True)
            logging.debug("Exiting script with exit code 2")
            quit(2)


# Sleep 15 seconds, this allows time for Syspro to import xml files before we start checking
logging.debug("Sleeping 15 seconds to let Rapi scp's finish (if any)")
time.sleep(15)

# Counter to count how many total 'o.xml' files we looked at
count = 0

# Counter to count how many new 'o.xml' files since last run
countNew = 0

# Counter to count how many po's not found
poNotFound = 0

# Iterate through all the 'o.xml' files and check if in syspro
logging.debug("Starting For loop through all xml files")
for fname in lst:
    if fname.endswith('o.xml') and fname != lastFileModifiedFilename:
        count += 1
        modtime = os.stat(os.path.join(fileDir, fname)).st_mtime
        if modtime > lastFileModified:  # Only check files who's modified time is more recent then the last file checked
            filesFound = True
            countNew += 1
            logging.debug("Found new file %s since last run" % fname)
            filesCollection.append(fname)
            poxmlquery = "//Orders/OrderHeader/CustomerPoNumber/text()"
            poNumber = parsexmlfile(fileDir + "/" + fname, poxmlquery)  # Get invoice number from o.xml file
            if poNumber is not False:
                if not len(poNumber):
                    logging.critical("'CustomerPoNumber' field is empty in xml file %s" % fileDir + "/" + fname)
                    logging.debug("Skipping this check and going to the next xml file if any left")
                    continue
                logging.debug("Found 'CustomerPoNumber' %s in file %s" % (poNumber[0], fname))
                queryresult = domssqlquery(poNumber[0], "invoice")  # Do api call to listener with invoice number
                logging.debug("PO query result = %s" % queryresult)
            else:
                logging.critical("Could not find 'CustomerPoNumber' field in file %s, skipping to the next xml file if any" % fname)
                # If we're not able to get a PO number from the o.xml file, still continue to process the remaining o.xml files
                continue
            if queryresult is not False:  # Successfully made api call, now check status in returned json object
                api_status = True
                if queryresult['query_result'] is not False:  # Invoice number found in Syspro
                    logging.debug("query_result: %s" % queryresult['query_result'])
                    logging.info("'CustomerPoNumber' %s found in Syspro database" % poNumber[0])
                    logging.debug("PO found in Syspro database with SalesOrder=%s and Customer=%s" % (queryresult['query_result']['SalesOrder'], queryresult['query_result']['Customer']))
                if queryresult['query_result'] is False:  # Invoice number NOT found in Syspro, Check if Customer is in Syspro
                    logging.debug("query_result: %s" % queryresult['query_result'])
                    logging.debug("'CustomerPoNumber' %s NOT FOUND in Syspro database so checking if 'Customer' exists" % poNumber[0])
                    customerxmlquery = "//Orders/OrderHeader/Customer/text()"
                    customer = parsexmlfile(fileDir + "/" + fname, customerxmlquery)  # Get customer number from o.xml file
                    if customer is False:
                        logging.critical("'Customer' field not found in o.xml file %s" % fileDir + "/" + fname)
                        logging.debug("Skipping this check and going to the next o.xml file if any left")
                        continue
                    if not len(customer):
                        logging.critical("'Customer' field is empty in o.xml file %s" % fileDir + "/" + fname)
                        logging.debug("Skipping this check and going to the next o.xml file if any left")
                        continue
                    logging.debug("Find 'Customer' in o.xml file returned = %s" % customer)
                    logging.debug("Looking up 'Customer' '%s' in Syspro database" % customer[0])
                    customerqueryresult = domssqlquery(customer[0], "customer")  # Do api call to listener with customer number
                    logging.debug("'Customer' query result = %s" % customerqueryresult)
                    if customerqueryresult is not False:  # Successfully made api call, now check status in returned json object
                        api_status = True
                        if customerqueryresult['query_result'] is not False:  # Customer found in Syspro
                            logging.debug("'Customer' %s found in Syspro database" % customer[0])
                            logging.critical("'CustomerPoNumber' %s NOT FOUND in Syspro database!" % poNumber[0])
                            logging.error("Check log file %s for instructions" % errorLogFilename)
                            poNotFound += 1
                            # Write to po log - po number, file name, False if customer does exist, customer number
                            lognotfoundinsyspro(poNumber[0], fname, False, customer[0])
                        if customerqueryresult['query_result'] is False:  # Customer NOT found in Syspro
                            logging.critical("'Customer' %s NOT FOUND in Syspro database so 'CustomerPoNumber' %s can't be imported in!" % (customer[0], poNumber[0]))
                            logging.error("Check log file %s for instructions" % errorLogFilename)
                            poNotFound += 1
                            # Write to po log - po number, file name, True if customer does not exist, customer number
                            lognotfoundinsyspro(poNumber[0], fname, True, customer[0])
                    else:  # API call failed
                        logging.debug("API call to query for customer %s failed!" % customer[0])
                        api_failure_count += 1
                        continue
            else:  # API call failed
                logging.debug("API call to query for invoice %s failed!" % poNumber[0])
                api_failure_count += 1
                continue
        else:
            queryresult = True  # Set to true if no files to check

# If we found any files to check put last file back into index file
if filesFound is not False:
    if api_status is False:  # API call failed
        logging.debug("Looped through %d total 'o.xml' files with %d new since last run and %d api call(s) failed to listener!" % (count, countNew, api_failure_count))
        logging.info("Done")
        print "Critical - API call to listener failed! See log file: %s" % debugLog
        quit(2)
    logging.debug("Looped through %d total 'o.xml' files with %d new since last run and %d PO's not found in Syspro database" % (count, countNew, poNotFound))
    logging.debug("Adding the last checked filename %s to index file" % filesCollection[-1])
    logging.info("Done")
    try:
        f = open(indexFile, 'w')
        f.write(filesCollection[-1] + "\n")
        f.close()
    except IOError as e:
        logging.critical("Error opening or writing to %s" % indexFile + " - I/O error({0}): {1}".format(e.errno, e.strerror), exc_info=True)
        logging.debug("Exiting script with exit code 2")
        quit(2)
    if poNotFound > 0:
        print "Critical - %d PO number(s) not found in Syspro! Check log %s" % (poNotFound, errorLogFilename)
        quit(2)
    else:
        print "OK - %d checked o.xml files are imported into Syspro" % count
        quit(0)
else:
    logging.info("No new files were found")
    logging.info("Done")
    print "OK - No new files were found"
    quit(0)
