# -*- coding: utf-8 -*-
"""
lambda_python_test.py

Description:
    This aws lambda test script will select from a mysql db the latest dump file name for database 'xxxxx'
"""

try:
    import mysql.connector
    from mysql.connector import errorcode
except ImportError:
    print "Module 'mysql.connector' not installed!  Exiting script"
    quit(2)


def doMysqlQuery(event, context):
    query_statement = "SELECT something from all_dbs LIMIT 1"

    # MySQL connection info
    config = {
        'user': 'mysql_db_backup',
        'password': '',
        'database': 'latest_mysql_db_backup',
        'host': '',
        'port': 3306,
        'connection_timeout': 10,
        'raise_on_warnings': True,
        'use_unicode': False,
    }

    class MySQLCursorDict(mysql.connector.cursor.MySQLCursor):
        def fetchone(self):
            row = self._fetch_row()
            if row:
                return dict(zip(self.column_names, self._row_to_python(row)))
            return None

    # Try to connect to the database
    try:
        cnx = mysql.connector.connect(**config)
        cursor = cnx.cursor(cursor_class=MySQLCursorDict)
    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Something is wrong with your mysql user name or password!")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database does not exists!")
        else:
            print("Something went wrong: {}".format(err))
            #cnx.close()
        quit(2)
    # Execute query
    cursor.execute(query_statement)
    results = cursor.fetchall()
    cursor.close()
    cnx.close()
    for result in results:
        return result[0]
