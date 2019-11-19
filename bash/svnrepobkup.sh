#!/bin/bash

# svnrepobkup.sh is a wrapper script around a python script that
#   was created to dump the subversion repos and copy them to another server
#   please do not modify this script without notifying 
#   11-24-2013

PROGNAME=`basename $0`
TMP=/tmp
NOW=$(date "+%Y%m%d%H%M%S")
DEBUGGING=true  # Enable or disable debug logging
DEBUGECHO=false # Whether or not to echo debugs to screen
DEBUGLOG=${TMP}/${PROGNAME}.log.${NOW}  # Debug log file
RECIPIENT=
NICE=`which nice`
NICELVL=15
HOSTNAME=`hostname`
OLDLOGDAYS=30  # Keep up to 30 days of logs
SKIPRSYNC=false # Set to true to skip rsync step

# Debugging function
function debug() {
    NOW=$(date "+%Y%m%d%H%M%S")
    if [ "$DEBUGGING" == "true" ] && [ "$DEBUGECHO" == "true" ]; then
        echo $1
        echo "$NOW: $1" >> $DEBUGLOG
    elif [ "$DEBUGGING" == "true" ]; then
        echo "$NOW: $1" >> $DEBUGLOG
    fi
}

# Email sending function
function sendemail() {
    # $1 = body of email
    # $2 = true/false whether to attach log to email
    SUBJECT="Error running $PROGNAME on $HOSTNAME"
    BODY="$1"
    #echo $BODY > $TMP/$PROGNAME.tmp 
    #echo "$BODY" | mail -s "$SUBJECT" "$RECIPIENT"
    if [ "$DEBUGGING" == "true" ]; then
        if [ "$2" == "true" ] || [ -z "$2" ]; then
            SVNREPOBKUPLOG=`ls -ltr /tmp/svnrepobkup*.log | awk -F ' ' '{print $9}' | tail -1`
	    debug "Emailing error email with log file attached: $SVNREPOBKUPLOG"
            #mutt -a "$DEBUGLOG" -s "$SUBJECT" $RECIPIENT < $TMP/$PROGNAME.tmp
            #echo "$BODY" | mutt -a "$DEBUGLOG" -s "$SUBJECT" -- $RECIPIENT
            echo "$BODY" | mutt -a "$SVNREPOBKUPLOG" -s "$SUBJECT" -- $RECIPIENT
	else
	    debug "Emailing error email"
	    echo "$BODY" | mutt -s "$SUBJECT" -- $RECIPIENT
	fi
    else
        echo "$BODY" | mutt -s "$SUBJECT" -- $RECIPIENT
        #mutt -s "$SUBJECT" $RECIPIENT < $TMP/$PROGNAME.tmp
    fi
    #rm $TMP/$PROGNAME.tmp
}

# Process started
debug "Starting $PROGNAME at: $(date) on $HOSTNAME"
START=$(date +%s)

# Error handling function
function onerror() {
    # Email the error
    # $1 = body of email
    # $2 = true/false whether to exit script
    # $3 = true/false whether to attach log to email
    #RECIPIENT="email@email.com"
    #SUBJECT="Error running svndump.sh on hostname"
    BODY="$1"
    #echo "$BODY" | mail -s "$SUBJECT" "$RECIPIENT"
    sendemail "$BODY" "$3"
    if [ "$2" == "true" ] || [ -z "$2" ]; then # check if we need to exit script or not
    	# Remove lock file dir
    	rmdir "$LOCKFILE"
    	exit 1
    fi
}

cd /root/svnrepobkup

suffix=$(date +%y%m%d)

# Create and/or check for lock file so this script doesn't run more than once at a time
LOCKFILE="/tmp/svnrepobkup_lock"
if mkdir "$LOCKFILE"; then
  debug "Locking succeeded - continuing..." 
else
  debug "Lock failed - exiting..."
  onerror "Lock failed - exiting..." "false" "false"
fi

# Execute python script to dump svn repos
/usr/bin/python /root/scripts/svnrepobkup.py
EXITCODE=$?
if [ "${EXITCODE}" -ne 0 ]; then
    SVNREPOBKUPLOG=`ls -ltr /tmp/svnrepobkup*.log | awk -F ' ' '{print $9}' | tail -1`
    if [ "${EXITCODE}" -eq 1 ]; then
    	debug "WARNING: svnrepobkup.py returned warning code: ${EXITCODE}! See $SVNREPOBKUPLOG for error(s)"
    	onerror "WARNING: svnrepobkup.py returned warning code: ${EXITCODE}! See $SVNREPOBKUPLOG for error(s)" "false" "true"
    else
    	debug "CRITICAL: svnrepobkup.py returned error code: ${EXITCODE}! See $SVNREPOBKUPLOG for error(s)"
    	onerror "CRITICAL: svnrepobkup.py returned error code: ${EXITCODE}! See $SVNREPOBKUPLOG for error(s)" "true" "true"
    fi
fi

debug "Rsyncing to server..."
# copy dump files off to another box
CMD=`rsync -avz -e 'ssh -ax -c arcfour' -q --timeout=30 /root/svnrepobkup/* backup@x.x.x.x:/home/backup/subversion_backup/svnrepobkup`
EXITCODE=$?
if [ "${EXITCODE}" -eq 0 ]; then
    debug "Finished rsync to server"
elif [ "${EXITCODE}" -eq 12 ]; then  # Get amount we are rsyncing and log that we need that much free space to rsync
    AMOUNTCOPYING=`du -sh /root/svnrepobkup | awk -F' ' '{print $1}'`
    debug "RSYNC failed to sync (exit code: ${EXITCODE}), need atleast ${AMOUNTCOPYING} of free space on server!"
    onerror "RSYNC failed to sync (exit code: ${EXITCODE}), need atleast ${AMOUNTCOPYING} of free space on server!" "false" "false" 
else
    debug "RSYNC error syncing to server x.x.x.x! RSYNC exit code: ${EXITCODE}"
    #echo $CMD
    #onerror "$CMD"
    onerror "RSYNC error syncing to server x.x.x.x! RSYNC exit code: ${EXITCODE}" "false" "false"
fi


if [ "${SKIPRSYNC}" == "false" ]; then
    # check if crashplan is mounted first
    mount | grep -i "/mnt/crashplan" >/dev/null 2>&1
    EXITCODE=$?
    if [ "${EXITCODE}" -ne 0 ]; then
        debug "Crashplan not mounted, exiting..."
        onerror "Crashplan not mounted, mount exit code: ${EXITCODE}  exiting..." "true" "false"
    else
        debug "Crashplan mounted"
    fi 
    debug "Rsyncing to Crashplan..."
    # Don't preserve perms, owner, or groups when rsyncing to nfs mount
    CMD=`rsync -avzq --no-p --no-o --no-g /root/svnrepobkup/* /mnt/crashplan/bkup/crashplan/subversion/svnrepobkup`
    EXITCODE=$?
    if [ "${EXITCODE}" -ne 0 ]; then
        debug "RSYNC error syncing to /mnt/crashplan! RSYNC exit code: ${EXITCODE}"
        #echo $CMD
        #onerror "$CMD"
        onerror "RSYNC error syncing to /mnt/crashplan! RSYNC exit code: ${EXITCODE}" "false" "false"
    else
        debug "Finished rsync to Crashplan nfs share"
        debug "Setting ownership of files on Crashplan nfs share"
        find /mnt/crashplan/bkup/crashplan/subversion/svnrepobkup -type f -print0 | xargs -0 chmod o+r
    fi
fi

# Delete log files older than OLDLOGDAYS var
if [ ! -z "${TMP}" ] && [ -d "${TMP}" ]; then
    debug "Deleting log files older than ${OLDLOGDAYS} days in ${TMP}"
    find "${TMP}" -maxdepth 1 -name "${PROGNAME}.log.*" -type f -mtime +${OLDLOGDAYS} -exec rm '{}' \;
    find "${TMP}" -maxdepth 1 -name "svnrepobkup_*.log" -type f -mtime +${OLDLOGDAYS} -exec rm '{}' \;
fi

# Remove lock file dir
rmdir "$LOCKFILE"

# Process ended
#echo ""
debug "Finished $PROGNAME at: $(date) on $HOSTNAME"
END=$(date +%s)
DIFF=$(( $END - $START ))
MINUTES=$(( $DIFF / 60 ))
#echo ""
debug "Script took $DIFF seconds or $MINUTES minutes."

exit
