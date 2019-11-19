#!/bin/bash

# This script wraps around cksfv from this website:
# http://zakalwe.fi/~shd/foss/cksfv/
#
# Script created 8-15-2017 by

print_usage() {
    echo ""
    #echo "Usage: $PROGNAME <src dir> <full path/sfv_file>"
    echo "Usage: $PROGNAME"
    echo ""
    echo "A menu choice of sfv files found will be displayed"
    echo ""
    echo "Note1: Existing <full path/sfv_file> will be deleted"
    echo "Note2: If existing .exclude file is found it will be used"
}

PROGNAME=`basename $0`

# Check if the user needs help
if test "$1" = "-h" -o "$1" = "--help" -o "$1" = "/?"; then
    print_usage
    exit 0
fi

declare -a SFVARRAY

# Check to see that all required commandline arguments are present
if [[ -z "$1" ]]; then
    for i in `ls *.sfv` 
    do
        SFVARRAY+=($i)
    done
    echo ""
    echo "Found the below SFV files in the current directory:"
    echo ${SFVARRAY[@]}
    echo ""
    #echo "Usage: $PROGNAME ${SFVARRAY[0]}"
    #echo ""
    #echo "You must provide all the required commandline arguments!"
    #exit 1
    MENUSFVSCRIPT="menusfvscripttmp.sh"
    GETSFV=$( 
    echo "#!/bin/bash" > $MENUSFVSCRIPT 
    echo "" >> $MENUSFVSCRIPT
    echo "PS3='Please choose an sfv file:'" >> $MENUSFVSCRIPT
    echo "select sfvfile in ${SFVARRAY[@]}; do" >> $MENUSFVSCRIPT
    echo "    echo \"\$sfvfile\"" >> $MENUSFVSCRIPT
    echo "    exit" >> $MENUSFVSCRIPT
    echo "done" >> $MENUSFVSCRIPT
    echo "" >> $MENUSFVSCRIPT
    echo "exit" >> $MENUSFVSCRIPT
    source ./$MENUSFVSCRIPT
    )
    SRCSFVFILE=$GETSFV
    rm $MENUSFVSCRIPT
else
    print_usage
    exit 0
fi

echo ""
echo "Executing $PROGNAME for '$SRCSFVFILE'..."
echo ""

# Get SRC_DIR from SFV_FILE
SRC_DIR=`grep -i 'src_dir' $SRCSFVFILE | awk -F' ' '{print $2}'`

# Get SFV_FILE from SFV_FILE
SFV_FILE=`grep -i 'sfv_file' $SRCSFVFILE | awk -F' ' '{print $2}'`

if [ -z $SRC_DIR ]; then echo "SRC_DIR not found in $SRCSFVFILE! Execute 'manual_mk_sfv.sh $SRCSFVFILE' to fix this..."; exit 1; fi
if [ -z $SFV_FILE ]; then echo "SFV_FILE not found in $SRCSFVFILE! Execute 'manual_mk_sfv.sh $SRCSFVFILE' to fix this..."; exit 1; fi
SFV_DIR=`dirname $SFV_FILE`
DEBUG=false

# true = run mk_sfv.sh quietly
mk_sfv.sh $SRC_DIR $SFV_FILE true
if [[ $? = 0 ]]; then
    if [[ -f "$SFV_FILE.exclude" ]]; then
        echo "Exclude file found running exclude_sfv.sh..."
        exclude_sfv.sh $SFV_FILE $SFV_FILE.exclude
	if [[ $? = 0 ]]; then
	    echo ""
	    echo "Removing excludes successful!"
	else
	    echo ""
	    echo "Removing excludes failed!"
	    exit 2
	fi
    else
        echo "No exclude file found."
    fi
else
    echo "Creating new/updated sfv file failed!"
    exit 2
fi

# Create original files list
#find $SRC_DIR -type f -name "*" | grep -v '\.svn' | grep -v '\.swp' | grep -v '\.ssh' > $SFV_FILE.origfilelist
#if [ -f $EXCLUDE_FILE ]; then
#    for line in `cat $EXCLUDE_FILE | grep -v ';'`;
#    do
#        echo "Removing '$line' from $SFV_FILE.origfilelist..."
#        grep -v "$line" $SFV_FILE.origfilelist > $SFV_FILE.origfilelist.tmp
#        mv $SFV_FILE.origfilelist.tmp $SFV_FILE.origfilelist
#    done
#fi

echo "Successfully updated $SFV_FILE"

exit
