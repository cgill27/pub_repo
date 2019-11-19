# -*- coding: utf-8 -*-
"""
check_syspro_invoice_listener.py

Description:
This script is a flask application that listens for api calls whitch contain
an invoice number to lookup in the Syspro database via mssql and return results

Last committed: $Date: 2014-10-23 16:38:33 -0500 (Thu, 23 Oct 2014) $
Revision number: $Revision: 272 $
Author: $Author: $
URL: $HeadURL: https://host/repo/check_syspro_invoice/check_syspro_invoice_listener.py $

"""
import os
from flask import Flask, request
from flask.ext import restful
from flask.ext.restful import Resource

try:
    # pymssql reference - http://pymssql.sourceforge.net/ref_pymssql.php
    import pymssql
except ImportError:
    print "No pymssql module installed!  Exiting"
    quit(2)
import datetime
import logging

# Get name, path, version of this script
script_name = __file__
script_path = os.path.dirname(os.path.abspath(__file__))
script_version = "$Id: check_syspro_invoice_listener.py 272 2014-10-23 21:38:33Z $"
app = Flask(__name__)
api = restful.Api(app)

# API key for client api calls
api_key = ""

# Microsoft SQL config vars (set for Syspro server)
mssql_config = {'user': 'pocheck', 'password': '', 'database': 'Syspro1', 'host': 'x.x.x.x', 'as_dict': True, 'timeout': 10, 'login_timeout': 15}

# Enable or disable debug logging
debugLevel = "debug"  # Set debugLevel to None to turn off logging
debugLog = "debug.log"

# Setup logging if specified at cli
if debugLevel:
    debugLevel = debugLevel.strip()
    debugLevel = debugLevel.lower()
    if debugLog:
        debugLog = str(debugLog)
        debugLog = debugLog.strip()
        if debugLog.find("TIMESTAMP") > 0:  # If the word 'TIMESTAMP' is found in debugLog, replace with debugLog_suffix
            # https://docs.python.org/2/library/time.html
            debugLog_suffix = datetime.datetime.now().strftime("%Y%m%d%H%M%S")  # 20130101235959  year month day hour minute second
            debugLog = debugLog.replace("TIMESTAMP", debugLog_suffix)
        debugLogDir = os.path.dirname(os.path.abspath(debugLog))
        if not os.path.isdir(debugLogDir):
            print "Option 'debugLog' needs to specify full path to a log file!  Exiting script"
            quit(2)
    else:
        print "If specifying debugLevel, also specify debugLog!  Exiting script"
        quit(2)
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
        quit(2)
    loggingEnabled = True
else:
    loggingEnabled = False
    debugLevel = ""
    debugLog = ""


def logger(log, level="debug"):
    """ Log to debugLog if logging enabled """
    if loggingEnabled:
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
logger("script_path = '%s'" % script_path, "debug")
logger("script_version = '%s'" % script_version, "info")
logger("api_key = '%s'" % api_key, "debug")
if debugLevel is not "":
    logger("debugLevel = '%s'" % debugLevel, "debug")
if debugLog is not "":
    logger("debugLog = '%s'" % debugLog, "debug")

# Variable to store messages from MS Sql
mssql_message = ""


def domssqlquery(query, config=mssql_config):
    """ Function to perform microsoft sql query (pass in query string) """
    global mssql_message
    logger("Starting microsoft sql query", "debug")
    try:
        conn = pymssql.connect(**config)
    except:
        logger("Unable to connect to Syspro database server!", "critical")
        mssql_message = "Unable to connect to Syspro database server!"
        return False
    cur = conn.cursor()
    try:
        logger("Executing query: %s" % query, "debug")
        cur.execute(query)
    except:
        conn.close()
        logger("Something went wrong with the sql query!", "critical")
        mssql_message = "Something went wrong with the sql query!"
        return False
    logger("Number of returned rows from sql query = %s" % cur.rowcount, "debug")
    mssql_message = "Number of returned rows from sql query = %s" % cur.rowcount
    results = cur.fetchone()
    conn.close()
    if cur.rowcount == 0:
        # No records found in database
        mssql_message = "No records found in Syspro database"
        return False
    elif cur.rowcount > 0 or cur.rowcount == -1:  # Not sure why -1 is returned when a row is found
        # PO found in database
        # return True
        mssql_message = "Record found in Syspro database"
        return results
    else:
        # Some other problem with records returned
        mssql_message = "Unable to get row count from results"
        return False


class GetInvoice(Resource):
    """ Get invoice or customer from json object and pass to function to query Syspro MS sql database
        Api response codes:
        200 OK The request was completed successfully.
        201 Created The request was completed successfully and a new resource was created as a result.
        400 Bad request The request is invalid or inconsistent.
        401 Unauthorized The request does not include authentication information.
        403 Forbidden The authentication credentials sent with the request are insufficient for the request.
        404 Not found The resource referenced in the URL was not found.
        405 Method not allowed The request method requested is not supported for the given resource.
        500 Internal server error An unexpected error has occurred while processing the request.
    """

    def post(self):  # Only accept POST verb, return 405 for all others
        client = request.remote_addr  # Log ip of client
        logger("Incoming request from: %s" % client, "info")
        if request.is_secure:  # Log if request came over HTTPS or not
            logger("HTTPS on")
        else:
            logger("HTTPS off")
        user_agent = request.user_agent  # Log user agent
        logger("User agent: %s" % user_agent, "debug")
        json_data = request.get_json(force=True)  # Decode incoming json object
        logger("Request json object posted: %s" % json_data, "debug")
        try:  # Check api key submitted
            submitted_api_key = json_data['api_key']
            logger("Submitted api_key: %s" % submitted_api_key, "debug")
        except KeyError:  # Uh oh api key does not match!
            logger("Invalid api_key", "critical")
            return "Invalid api_key", 401
        if submitted_api_key is None or submitted_api_key == "" or submitted_api_key != api_key:
            logger("Invalid api_key", "critical")
            return {"Invalid api_key": submitted_api_key}, 401
        try:  # Is this a query or ping api call being made?
            operation = json_data['operation']
        except KeyError:
            logger("operation (query or ping) not specified", "critical")
            return "operation (query or ping) not specified", 400
        if operation == "ping":
            return {"ping": "successful"}, 200
        elif operation == "query":
            try:
                customer_or_invoice = json_data['customer_or_invoice']
                logger("customer_or_invoice: %s" % customer_or_invoice, "debug")
            except KeyError:
                logger("customer_or_invoice not specified", "critical")
                return "customer_or_invoice not specified", 400
            if customer_or_invoice is None or customer_or_invoice == "":
                logger("customer_or_invoice not specified", "critical")
                return "customer_or_invoice not specified", 400
            if customer_or_invoice == "invoice":
                try:
                    invoice = json_data['invoice']
                    logger("invoice: %s" % invoice, "debug")
                except KeyError:
                    logger("No invoice specified", "critical")
                    return "No invoice specified", 400
                if invoice is None or invoice == "":
                    logger("No invoice specified", "critical")
                    return {"No invoice specified"}, 400
                if invoice.find(",") > 0:  # If comma seperated list of invoices sent, check each one
                    invoices = invoice.split(",")
                    invoices_list = []
                    for i in invoices:
                        poquery = "SELECT SalesOrder,Customer FROM dbo.SorMaster WHERE CustomerPoNumber = '%s'" % i
                        queryresult = domssqlquery(poquery)
                        invoices_list.append({"invoice": i, "query_status": mssql_message, "query_result": queryresult})
                    return_msg = invoices_list
                    logger("Returning: %s" % return_msg, "info")
                    return return_msg, 200
                else:
                    poquery = "SELECT SalesOrder,Customer FROM dbo.SorMaster WHERE CustomerPoNumber = '%s'" % invoice
                    queryresult = domssqlquery(poquery)
                    logger("queryresult: %s" % queryresult, "debug")
                    if queryresult is False:
                        return_msg = {"invoice": invoice, "query_status": mssql_message, "query_result": queryresult}
                        logger("Returning: %s" % return_msg, "info")
                        return return_msg, 200
                    else:
                        return_msg = {"invoice": invoice, "query_status": mssql_message, "query_result": queryresult}
                        logger("Returning: %s" % return_msg, "info")
                        return return_msg, 200
            elif customer_or_invoice == "customer":
                try:
                    customer = json_data['customer']
                    logger("customer: %s" % customer, "debug")
                except KeyError:
                    logger("No customer specified", "critical")
                    return "No customer specified", 400
                if customer is None or customer == "":
                    logger("No customer specified", "critical")
                    return "No customer specified", 400
                customer_query = "SELECT Customer FROM dbo.ArCustomer WHERE Customer = '%s'" % customer
                queryresult = domssqlquery(customer_query)
                logger("queryresult: %s" % queryresult, "debug")
                return_msg = {"customer": customer, "query_status": mssql_message, "query_result": queryresult}
                logger("Returning: %s" % return_msg, "info")
                return return_msg, 200
        else:
            logger("operation (query or ping) not specified", "critical")
            return "operation (query or ping) not specified", 400


api.add_resource(GetInvoice, "/")

if __name__ == '__main__':
    #app.run(debug=True)
    app.run()
