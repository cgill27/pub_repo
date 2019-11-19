# -*- coding: utf-8 -*-
"""
transcode_video.py

Description:
This script takes cli arguments to transcode an input mp4 video to
    3 different resolutions and a fast (1.5x) speedup of each

External script requirements:
    ffmpeg (with ladspa plugin)
    mencoder

Last committed: $Date: 2017-11-28 15:49:40 -0600 (Tue, 28 Nov 2017) $
Revision number: $Revision: 410 $
Author: $Author: cgill $
URL: $HeadURL: https://localhost/video_encoding/transcode_video.py $

"""

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
import sys
import logging
from datetime import datetime
import time
import subprocess, shlex
from fnmatch import fnmatch
import tempfile
import random, string

# Check Python version and exit if not atleast 2.7
req_version = (2, 7)
cur_version = os.sys.version_info

if not cur_version >= req_version:
    print "Your Python interpreter is too old. Please consider upgrading to atleast 2.7"
    quit(2)

# If False then no logs are created, only the status at the end is displayed
debug = True

# Echo log to screen if set to True
print_log = True

# Get name, path, version of this script
script_name = __file__
script_path = os.path.dirname(os.path.abspath(__file__))
script_version = "$Id: transcode_video.py 410 2017-11-28 21:49:40Z cgill $"


def printhelp():
    # Show help options
    if figlet_installed is True:
        f = Figlet(font='slant')
        print f.renderText(script_name)
    print " "
    print "This script takes cli arguments to transcode an input mp4 video to"
    print "  3 different resolutions and a fast (1.5x) speedup of each"
    print " "
    print "Usage: %s -i /full/path/to/inputfile -o /full/path/to/outputdir" % script_name
    print " "
    print "Required args:"
    print "-i | --inputfile        Input mp4 file"
    print "-o | --outputdir        Output directory"
    print " "
    print "Optional args:"
    print "-m | --metatitle        Video title meta tag"
    print "-d | --debuglevel       Level of logging (debug, info, warning, error, critical)"
    print "-l | --debuglog         Log file to log to (full path)"
    print "-v | --version          Show script version info"
    print "Note: if 'TIMESTAMP' is in debugLog file name, it will be substituted with a timestamp"
    print "Note2: 'debug = True' must be set in script for logging to happen"
    print " "
    print "Help: %s -h" % script_name
    print " "
    quit(1)


# Parse cli options
parser = argparse.ArgumentParser(description="This script takes cli arguments to transcode an input mp4 video to predefined outputs")
#   Required args
parser.add_argument("-i", "--inputfile", help="Full path to the input file to read", type=str)
parser.add_argument("-o", "--outputdir", help="Full path to the output directory", type=str)
#   Optional args
parser.add_argument("-m", "--metatitle", type=str, help="Video title meta tag")
parser.add_argument("-d", "--debugLevel", type=str, choices=["debug", "info", "warning", "error", "critical"], help="Set debug level")
parser.add_argument("-l", "--debugLog", type=str, help="Debug log file name if debugLevel is set")
parser.add_argument("-v", "--version", action="version", version="$Id: transcode_video.py 410 2017-11-28 21:49:40Z cgill $")
# Check for help argument and print help
if "-h" in sys.argv or "--help" in sys.argv:
    printhelp()
# Print help if we don't have all the required args
if len(sys.argv) < 2:
    print " "
    print "Input file is a required argument! Exiting script"
    printhelp()
args = parser.parse_args()

# Get required cli args
if hasattr(args, "inputfile") and args.inputfile is not None:
    input_file = args.inputfile
    input_file = input_file.strip()
    input_file_full_path = os.path.abspath(input_file)  # Get full path to input file
    if not os.path.exists(input_file_full_path) or not os.path.isfile(input_file_full_path):
        print "Input file '%s' does not exist or is not a file!  Exiting script" % input_file_full_path
        quit(2)
    input_file_name = os.path.basename(input_file_full_path)  # Get just file name of input file
    input_file_no_ext = os.path.splitext(os.path.basename(input_file_name))[0]  # Get just the input file name with no extension
    input_file_no_ext = input_file_no_ext.replace(' ', '_')  # Replace spaces in input file name with underscores
else:
    print "Input file is a required argument! Exiting script"
    quit(2)

if hasattr(args, "outputdir") and args.outputdir is not None:
    output_dir = args.outputdir
    output_dir = output_dir.strip()
    output_dir_full_path = os.path.abspath(output_dir)  # Get full path to output dir if not specified full path at cli
    if not os.path.exists(output_dir_full_path) or not os.path.isdir(output_dir_full_path):
        print "Output directory '%s' does not exist or is not a directory!  Exiting script" % output_dir_full_path
        quit(2)
else:
    print "Output directory is a required argument! Exiting script"
    quit(2)


# Get optional cli args
video_meta_title = ""  # Default to no meta title
if hasattr(args, "metatitle") and args.metatitle is not None:
    video_meta_title = args.metatitle
    video_meta_title = video_meta_title.strip()
else:
    video_meta_title = ""

# Setup logging if specified at cli
if hasattr(args, "debugLevel") and args.debugLevel is not None:
    debugLevel = args.debugLevel
    debugLevel = debugLevel.strip()
    if hasattr(args, "debugLog"):
        debugLog = args.debugLog
        debugLog = str(debugLog)
        debugLog = debugLog.strip()
        if debugLog.find("TIMESTAMP") > 0:  # If the word 'TIMESTAMP' is found in debugLog argument, replace with debugLog_suffix
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
        if print_log is True:
            print level + ": %s" % log
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
logger("input_file = '%s'" % input_file_full_path, "debug")
logger("output_dir = '%s'" % output_dir_full_path, "debug")


def ffprobe(ffprobe_input_file):
    """ This function will shell out to 'ffprobe' to show stats on video input file
        Make sure 'ffmpeg' is installed! """
    if ffprobe_input_file == "" or ffprobe_input_file is None:
        return False
    exec_cmd = ['/usr/bin/ffprobe', '-print_format', 'json', '-show_streams', ffprobe_input_file]
    try:
        p = subprocess.Popen(exec_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as err:
        logger("ffprobe: subprocess.Popen returned error: %s" % err, "critical")
        return False
    pid = p.pid
    logger("Running '%s', PID = %s" % (str(exec_cmd), pid), "info")
    cmdoutput, cmderr = p.communicate()  # Wait until subprocess cmd finishes and capture stdout/stderr
    retcode = p.returncode
    if retcode > 0:
        logger("ffprobe: Non-zero exit code '%d' returned from '%s' with error '%s'" % (retcode, str(exec_cmd), cmderr), "critical")
        return False
    else:  # Command was executed with 0 exit code - success
        logger("ffprobe: %s" % cmdoutput, "debug")
        return True


def mencoder(mencoder_cmd):
    """ This function will shell out to 'mencoder' to transcode video to 1.5x speed
        Make sure 'mencoder' is installed! """
    if mencoder_cmd == "" or mencoder_cmd is None:
        return False
    logger("mencoder: %s" % mencoder_cmd, "debug")
    exec_cmd = shlex.split(mencoder_cmd)
    try:
        p = subprocess.Popen(exec_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as err:
        logger("mencoder: subprocess.Popen returned error: %s" % err, "critical")
        return False
    pid = p.pid
    logger("Running '%s', PID = %s" % (mencoder_cmd, pid), "info")
    cmdoutput, cmderr = p.communicate()  # Wait until subprocess cmd finishes and capture stdout/stderr
    retcode = p.returncode
    if retcode > 0:
        logger("mencoder: Non-zero exit code '%d' returned from '%s' with error '%s'" % (retcode, mencoder_cmd, cmderr), "critical")
        return False
    else:  # Command was executed with 0 exit code - success
        return True


def ffmpeg(ffmpeg_cmd):
    """ This function will shell out to 'ffmpeg' to encode video to the 3 different resolutions
            Make sure 'ffmpeg' is installed! """
    if ffmpeg_cmd == "" or ffmpeg_cmd is None:
        return False
    logger("ffmpeg: %s" % ffmpeg_cmd, "debug")
    exec_cmd = shlex.split(ffmpeg_cmd)
    try:
        p = subprocess.Popen(exec_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except OSError as err:
        logger("ffmpeg: subprocess.Popen returned error: %s" % err, "critical")
        return False
    pid = p.pid
    logger("Running '%s', PID = %s" % (ffmpeg_cmd, pid), "info")
    cmdoutput, cmderr = p.communicate()  # Wait until subprocess cmd finishes and capture stdout/stderr
    retcode = p.returncode
    if retcode > 0:
        logger("ffmpeg: Non-zero exit code '%d' returned from '%s' with error '%s'" % (retcode, ffmpeg_cmd, cmderr), "critical")
        return False
    else:  # Command was executed with 0 exit code - success
        return True


def makedirectory(directory_name):
    """ Create a directory """
    directoryname = os.path.abspath(directory_name)
    logger("Creating directory '%s'" % directoryname, "debug")
    if not os.path.exists(directoryname) and not os.path.isdir(directoryname):
        try:
            os.mkdir(directory_name)
            return True
        except OSError as e:
            logger("makedirectory: Error creating directory '%s'!" % directoryname + " - I/O error({0}): {1}".format(e.errno, e.strerror), "critical")
            return False
    else:
        logger("makedirectory: Directory '%s' already exists!" % directoryname, "debug")
        return False


def randomstring(length):
    """ Return a random string of characters of the given length """
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(length))


def delfile(file_to_delete):
    if os.path.isfile(file_to_delete) is True:
        try:
            os.remove(file_to_delete)
            logger("delfile: Successfully deleted file '%s'" % file_to_delete, "debug")
            return True
        except OSError as e:
            logger("delfile: Error deleting file '%s'!" % file_to_delete + " - I/O error({0}): {1}".format(e.errno, e.strerror), "critical")
            return False
    else:
        logger("delfile: File '%s' is not a file so can't delete it" % file_to_delete, "warning")
    return False


# Create output directory to contain all output files (based off input file name)
if makedirectory(output_dir_full_path + "/" + input_file_no_ext) is False:
    logger("Error creating directory '%s'!  See debug log  Exiting script" % input_file_no_ext, "critical")
    #print "Error creating directory '%s'!  See debug log  Exiting script" % input_file_no_ext
    quit(2)

# FFMPEG/mencoder variables for transcoding
mencoder_speed_dict = {15: "1.5"}  # multiple speeds can be done, we only do 1.5x speed at this time
resolution_dict = {240: "428:240 -b:v 150k", 360: "640:360 -b:v 320k", 480: "854:480 -b:v 650k"}  # Resolution and streaming bitrate
ffmpeg_bin = "/usr/bin/ffmpeg "
mencoder_bin = "/usr/bin/mencoder "
ladspa_bin = "/usr/lib/ladspa/tap_pitch"  # Ladspa plugin we use to do pitch bend for 1.5x speed

# Ffprobe input video file
logger("Running ffprobe against input file '%s'" % input_file_full_path, "debug")
#ffprobe("'" + input_file_full_path + "'")
ffprobe(input_file_full_path)

### Start 1.5x speed encoding
# First do mencoder speed adjustment to input video
for speeds, speed in mencoder_speed_dict.iteritems():  # Loop over the 3 resolutions and create output video at 1.5x speed
    mencoder_options = " -speed " + speed + " -af ladspa=" + ladspa_bin + ":tap_pitch:0:-33:-90:0 -ovc copy -oac pcm -o "
    temp_mencoder_file = output_dir_full_path + "/" + input_file_no_ext + "/" + input_file_no_ext + "_speed_" + str(speeds) + "x_" + randomstring(7) + ".mp4"
    logger("Creating temp file name '%s' in directory '%s'" % (temp_mencoder_file, output_dir_full_path + "/" + input_file_no_ext))
    mencoder_cmd = mencoder_bin + "\"" + input_file_full_path + "\"" + mencoder_options + temp_mencoder_file
    logger("# mencoder 1.5x speed encode", "debug")
    logger("mencoder_cmd: %s" % mencoder_cmd, "debug")
    run_mencoder = mencoder(mencoder_cmd)
    if run_mencoder is True:
        # Ffprobe mencoded output file
        ffprobe(temp_mencoder_file)
        # Second do ffmpeg pass 1 to create stats log file that will be used by pass 2
        for key, resolution in resolution_dict.iteritems():
            pass_log_file = output_dir_full_path + "/" + input_file_no_ext + "/" + str(key) + "_fast"
            transcode_first_pass_options = " -y -pass 1 -c:a aac -c:v libx264 -preset medium -keyint_min 30 -r 30000/1001 -g 30 -threads 0 -vf scale=" + resolution + " -f mp4 -stats -passlogfile " + pass_log_file + " /dev/null"
            ffmpeg_pass1_cmd = ffmpeg_bin + "-i " + temp_mencoder_file + transcode_first_pass_options
            logger("# ffmpeg pass 1 res: %d" % key, "debug")
            logger("ffmpeg_pass1_cmd: %s" % ffmpeg_pass1_cmd, "debug")
            run_ffmpeg_pass1 = ffmpeg(ffmpeg_pass1_cmd)
            if run_ffmpeg_pass1 is True:
                # Third do ffmpeg pass 2 using stats output file from pass1 and create our final output video file
                transcode_second_pass_options = " -y -pass 2 -c:a aac -c:v libx264 -preset medium -profile:v main -level 3.1 -keyint_min 30 -r 30000/1001 -g 30 -threads 0 -vf scale=" + resolution + " -movflags +faststart -copyright on -metadata title=\"" + video_meta_title + "\" -stats -passlogfile " + pass_log_file + " "
                ffmpeg_pass2_cmd = ffmpeg_bin + "-i " + temp_mencoder_file + transcode_second_pass_options + output_dir_full_path + "/" + input_file_no_ext + "/" + str(key) + "_fast.mp4"
                logger("# ffmpeg pass 2 res: %d" % key, "debug")
                logger("ffmpeg_pass2_cmd: %s" % ffmpeg_pass2_cmd, "debug")
                run_ffmpeg_pass2 = ffmpeg(ffmpeg_pass2_cmd)
                if run_ffmpeg_pass2 is True:
                    # Ffprobe pass 2 output file
                    ffprobe(output_dir_full_path + "/" + input_file_no_ext + "/" + str(key) + "_fast.mp4")
                    logger("Successfully completed fast version of %d file!  Continuing" % key, "info")
                else:
                    logger("Ffmpeg returned non-zero exit code in %d pass 2!  Exiting script" % key, "critical")
                    logger("Deleting temp_mencode_file '%s'" % temp_mencoder_file, "debug")
                    delfile(temp_mencoder_file)
                    quit(2)
            else:
                logger("Ffmpeg returned non-zero exit code in %d pass 1!  Exiting script" % key, "critical")
                logger("Deleting temp_mencode_file '%s'" % temp_mencoder_file, "debug")
                delfile(temp_mencoder_file)
                pass_log_filename_log = pass_log_file + "-0.log"
                pass_log_filename_mbtree = pass_log_file + "-0.log.mbtree"
                logger("Deleting pass_log_file '%s'" % pass_log_filename_log, "debug")
                delfile(pass_log_filename_log)
                logger("Deleting pass_log_file '%s'" % pass_log_filename_mbtree, "debug")
                delfile(pass_log_filename_mbtree)
                quit(2)
            # Cleanup temporary ffmpeg stats log files
            pass_log_filename_log = pass_log_file + "-0.log"
            pass_log_filename_mbtree = pass_log_file + "-0.log.mbtree"
            logger("Deleting pass_log_file '%s'" % pass_log_filename_log, "debug")
            delfile(pass_log_filename_log)
            logger("Deleting pass_log_file '%s'" % pass_log_filename_mbtree, "debug")
            delfile(pass_log_filename_mbtree)

    else:
        logger("Mencoder returned non-zero exit code!  Exiting script", "critical")
        logger("Deleting temp_mencoder_file '%s'" % temp_mencoder_file, "debug")
        delfile(temp_mencoder_file)
        quit(2)

# Cleanup temporary file used for mencoder above
if os.path.isfile(temp_mencoder_file) is True: delfile(temp_mencoder_file)

#print " "
#print " "
#print " "

### Start regular speed encoding
# First do ffmpeg pass 1 to create stats log file that will be used by pass 2
for key, resolution in resolution_dict.iteritems():  # Loop over the 3 resolutions and create output video
    pass_log_file = output_dir_full_path + "/" + input_file_no_ext + "/" + str(key)
    transcode_first_pass_options = " -y -pass 1 -c:a aac -c:v libx264 -preset medium -keyint_min 30 -r 30000/1001 -g 30 -threads 0 -vf scale=" + resolution + " -f mp4 -stats -passlogfile " + pass_log_file + " /dev/null"
    ffmpeg_pass1_cmd = ffmpeg_bin + "-i " + "\"" + input_file_full_path + "\"" + transcode_first_pass_options
    logger("# ffmpeg pass 1 res: %d" % key, "debug")
    logger("ffmpeg_pass1_cmd: %s" % ffmpeg_pass1_cmd, "debug")
    run_ffmpeg_pass1 = ffmpeg(ffmpeg_pass1_cmd)
    if run_ffmpeg_pass1 is True:
        # Second do ffmpeg pass 2 using stats output file from pass1 and create our final output video file
        transcode_second_pass_options = " -y -pass 2 -c:a aac -c:v libx264 -preset medium -profile:v main -level 3.1 -keyint_min 30 -r 30000/1001 -g 30 -threads 0 -vf scale=" + resolution + " -movflags +faststart -copyright on -metadata title=\"" + video_meta_title + "\" -stats -passlogfile " + pass_log_file + " "
        ffmpeg_pass2_cmd = ffmpeg_bin + "-i " + "\"" + input_file_full_path + "\"" + transcode_second_pass_options + output_dir_full_path + "/" + input_file_no_ext + "/" + str(key) + ".mp4"
        logger("# ffmpeg pass 2 res: %d" % key, "debug")
        logger("ffmpeg_pass2_cmd: %s" % ffmpeg_pass2_cmd, "debug")
        run_ffmpeg_pass2 = ffmpeg(ffmpeg_pass2_cmd)
        if run_ffmpeg_pass2 is True:
            # Ffprobe pass 2 output file
            ffprobe(output_dir_full_path + "/" + input_file_no_ext + "/" + str(key) + ".mp4")
            logger("Successfully completed %d file!  Continuing" % key, "info")
        else:
            logger("Ffmpeg returned non-zero exit code in %d pass 2!  Exiting script" % key, "critical")
            quit(2)
    else:
        logger("Ffmpeg returned non-zero exit code in %d pass 1!  Exiting script" % key, "critical")
        pass_log_filename_log = pass_log_file + "-0.log"
        pass_log_filename_mbtree = pass_log_file + "-0.log.mbtree"
        logger("Deleting pass_log_file '%s'" % pass_log_filename_log, "debug")
        delfile(pass_log_filename_log)
        logger("Deleting pass_log_file '%s'" % pass_log_filename_mbtree, "debug")
        delfile(pass_log_filename_mbtree)
        quit(2)
    # Cleanup temporary files used for above encoding
    pass_log_filename_log = pass_log_file + "-0.log"
    pass_log_filename_mbtree = pass_log_file + "-0.log.mbtree"
    logger("Deleting pass_log_file '%s'" % pass_log_filename_log, "debug")
    delfile(pass_log_filename_log)
    logger("Deleting pass_log_file '%s'" % pass_log_filename_mbtree, "debug")
    delfile(pass_log_filename_mbtree)


script_end_time = time.time()
total_script_time = script_end_time - script_start_time
logger("Script took %d seconds to run" % total_script_time, "debug")
logger("Done", "info")
