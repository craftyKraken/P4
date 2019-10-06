'''
Utility wrapper for control of Canon EOS 80D camera via gphoto2 over USB.

All functions assume camera is set to bulb mode for manual exposure timing.

Author: James Chamness
Version: 1.0 (October 6, 2019)

'''

import logging
import RPi.GPIO as GPIO
import os, subprocess, sys, time

def verifyCameraConnect(logger):
    '''Return boolean readout for whether camera is attached.
    
    Implementation is based on a string search for the camera name using the
    gphoto2 --auto-detect command. If using a different camera, this hardcoded
    search value must be modified. 
    
    NOTE: this may not be the best way to verify camera connection, since I
    have observed that sometimes the camera still remains visible to the auto-
    detect call, even after being powered off. A better implementation might
    therefore be to perform some trivial ping that requires camera response...
    
    Furthermore it seems that powering off the camera doesn't remove it from the
    auto-detect list, but unplugging the USB cable after powering it off does.
    When I plug the USB back in, it does not become visible, until/unless I
    power the camera on again...
    '''
    
    verified = False
    
    logger.debug('Verifying gPhoto2 and camera interface')
    verify_camera_connect_cmdstr = 'gphoto2 --auto-detect'
    logger.debug('    Autodetecting camera...')
    output = subprocess.run(verify_camera_connect_cmdstr, shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
    for row in output.split('\n'):
        if 'Canon EOS 80D' in row:
            verified = True
    if not verified:
        logger.debug('    WARNING: camera NOT found!')
    else:
        logger.debug('    Found: Canon EOS 80D')
        
    return verified

def verifyBulbMode(logger):
    '''Return boolean readout for whether camera is set to bulb mode.
    
    Implementation is based on the fact that the only shutterspeed option
    available under bulb mode is 'bulb', and this is visible as the current
    setting.
    '''
    
    verified = False
    
    check_shutterspeed_set_cmdstr = 'gphoto2 --get-config shutterspeed'
    output = subprocess.run(check_shutterspeed_set_cmdstr, shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
    for row in list(map(lambda x: x.strip(), output.split('\n'))):
        if not len(row) == 0:
            if 'Current:' in row:
                if 'bulb' in row:
                    logger.debug('Bulb mode verified')
                    verified = True
                else:
                    logger.debug('Camera is NOT in bulb mode! Please fix before using program')
    return verified

def killMonitorProcess(logger):
    '''Kill troublesome gphoto2 processes to enable camera control.
    
    There is/are some background process(es) spawned by gphoto2 that block most
    camera control commands from being executed. I've tried a few different ways
    to circumvent this issue, but the most thorough way is to do a kill for all
    processes with 'gvfs' in the name.
    
    The process will be running by default even if a camera is not connected.
    
    Note: consider a routine to verify obstruction prior to killing processes,
    because it's not always necessary (e.g. if this has already been called).
    The same routine would be a good verification for access release once this
    function is called.
    '''
    
    logger.debug('    Killing monitor process to permit camera control access...')
    
    # Strategy 1: identify obstructing process by PID matching for
    # 'gvfs-gphoto2-volume-monitor process'. Turns out this doesn't always work,
    # possibly because child processes are spawned by this parent...
    
#     find_monitor_proc_ids_cmdstr = "ps aux | grep 'gvfs-gphoto2-volume-monitor' | awk '{print $2}'"
#     output = subprocess.run(find_monitor_proc_ids_cmdstr, shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
#     pid = -1
#     for row in list(map(lambda x: x.strip(), output.split('\n'))):
#         if not len(row) == 0:
#             #print('$' + row)
#             proc_lookup = subprocess.run(['ps','-p',row], stdout=subprocess.PIPE).stdout.decode('utf-8')
#             for line in list(map(lambda x: x.strip(), proc_lookup.split('\n'))):
#                 #print('#' + line)
#                 if not len(line) == 0 and not "PID" in line:
#                     pid = line[:line.find(' ')]
#                     subprocess.run(['kill',pid], stdout=subprocess.PIPE).stdout.decode('utf-8')
#                     logger.debug('    Killed monitor parent process (PID = ' + pid + ')')
#     if pid == -1:
#         logger.debug('    No monitor process found.')
    
    # Strategy 2: child processes have rapidly varying PIDs, such that a serial
    # procedure to first search for PIDs then kill them fails to get them all.
    # This is the brute force method, killing all procs with a 'gvfs' string
    # match in a single bash call.
    find_monitor_proc_ids_cmdstr = "ps aux | grep 'gvfs' | awk '{print $2}'"
    output = subprocess.run(find_monitor_proc_ids_cmdstr, shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
    pid = -1
    for row in list(map(lambda x: x.strip(), output.split('\n'))):
        if not len(row) == 0:
            #print('$' + row)
            proc_lookup = subprocess.run(['ps','-p',row], stdout=subprocess.PIPE).stdout.decode('utf-8')
            for line in list(map(lambda x: x.strip(), proc_lookup.split('\n'))):
                #print('#' + line)
                if not len(line) == 0 and not "PID" in line:
                    pid = line[:line.find(' ')]
                    subprocess.run(['kill',pid], stdout=subprocess.PIPE).stdout.decode('utf-8')
                    logger.debug('    Killed monitor parent process (PID = ' + pid + ')')
    if pid == -1:
        logger.debug('    No monitor process found.')
    return

def initRelayControl(logger):
    '''Setup code for the power relay(s), default OFF.
    '''
    logger.debug('Initializing GPIO relay control...')
    GPIO.setwarnings(False) #turn off warnings
    GPIO.cleanup() # reset any previous settings that may have been run
    GPIO.setmode(GPIO.BCM) # control pins by BCM number, NOT native Pi number
    GPIO.setup(2, GPIO.OUT, initial=GPIO.LOW) # setup channel for BCM pin #2 with relay initially off
    time.sleep(2) # buffer time for switch to actuate
    logger.debug('...done')
    
    return True

def readConfFile(filename, capture_profile='single'):
    '''Parse capture options from configuration file.
    
    Configuration file format: one key-value pair per line, separated by a
    single '=' character. Empty lines and any line content following  '#'
    character are ignored. All whitespace flanking keys and values is ignored.
    Internal whitespace chars (i.e. for subject name) are permitted but not
    recommended.
    
    Current QC step only ensures that an argument is supplied for each of and
    only the required parameters; argument validity is to be handled downstream.
    
    filename -- full path to config file
    capture_profile -- ['single', 'series', 'dual_series'] are currently permissable options
    lights -- ['on', 'off'] are permissable options
    '''
    
    with open(filename) as f:
        lines = list(map(lambda x: x.strip(), f.readlines()))
    conf = {}
    for line in lines:
        if line.strip() == '':
            continue
        if '#' in line:
            line = line[:line.find('#')]
        key, value = list(map(lambda x: x.strip(), line.split('=')))
        conf[key] = value
    if capture_profile == 'single':
        if not len(conf) == 5:
            print('Mismatch between number of required and specified configurable parameters!')
        if not sorted(conf.keys()) == ['aperture', 'iso', 'lights', 'shutterspeed', 'subject']:
            print('Missing a required configurable parameter!')
    elif capture_profile == 'series':
        if not len(conf) == 7:
            print('Mismatch between number of required and specified configurable parameters!')
        if not sorted(conf.keys()) == ['aperture', 'duration', 'interval', 'iso', 'shutterspeed', 'subject', 'lights']:
            print('Missing a required configurable parameter!')
    elif capture_profile == 'dual_series':
        if not len(conf) == 9:
            print('Mismatch between number of required and specified configurable parameters!')
        if not sorted(conf.keys()) == ['aperture_dark', 'aperture_light', 'duration', 'interval', 'iso_dark', 'iso_light', 'shutterspeed_dark', 'shutterspeed_light', 'subject']:
            print('Missing a required configurable parameter!')
    else:
        print('Unreachable code!')
    return conf

def loadconfigurableParameterDicts(aperture_dict_filename, iso_dict_filename):
    '''Load from file: dictionaries mapping indices to values for various
    configurable parameters.
    
    I made files with these values hardcoded for easy parsing; these values are
    also specific to the 80D, and need to be redone for a new camera.
    
    Also, the list of optionable arguments for some parameters changes depending
    on the camera mode: for example, shutterspeed in bulb mode has only one
    option, 'bulb', whereas in manual mode it has an extended list. FWIW it
    seems to the case that aperture and ISO, the only ones I've implemented so
    far here, are unchanged in bulb mode vs. full manual. 
    '''
    
    aperture_dict = {}
    with open(aperture_dict_filename) as f:
        for line in f.readlines():
            if not "INDEX" in line:
                aperture_dict[line.split('\t')[0]] = line.split('\t')[1].strip()
    iso_dict = {}
    with open(iso_dict_filename) as f:
        for line in f.readlines():
            if not "INDEX" in line:
                iso_dict[line.split('\t')[0]] = line.split('\t')[1].strip()
    return aperture_dict, iso_dict

def setParameterByValue(logger, setting, value):
    '''Change a configurable camera setting to a specified value by value, and
    verify that setting was accepted. Return True iff parameter is successfully
    verified.
    
    Accepted arguments for 'setting': ["aperture", "iso"]
    
    For accepted values for each setting, see the dictionary file for each
    parameter or run the --get-config command.
    
    NOTE: consider implementing more of these, i.e. shutterspeed, raw format,
    etc. depending on camera mode.
    '''
    
    # check that setting and parameter arguments are valid
    if not setting in ['aperture', 'iso']:
        logger.debug('WARNING: "' + setting + '" is not a configurable parameter')
        logger.debug('Exit setParameterByValue()')
        return False
    aperture_dict_filename = '/home/pi/pipeline/80D_aperture_dict' # these text files should be placed in the same directory as the script
    iso_dict_filename = '/home/pi/pipeline/80D_iso_dict'
    aperture_dict, iso_dict = loadconfigurableParameterDicts(aperture_dict_filename, iso_dict_filename)    
    if setting == 'aperture':
        dictionary = aperture_dict
    elif setting == 'iso':
        dictionary = iso_dict
    else:
        print("unreachable")
    if not value in dictionary.values():
        logger.debug('WARNING: "' + value + '" is not an accepted value for the "' + setting + '" parameter')
        logger.debug('Exit setParameterByValue()')
        return False
    
    logger.debug('\tSetting ' + setting + ' parameter to ' + str(value) + '...')
    
    # check current value to assess change need
    get_setting_cmd = ['gphoto2', '--get-config', setting]
    output = subprocess.run(get_setting_cmd, stdout=subprocess.PIPE).stdout.decode('utf-8')
    for row in list(map(lambda x: x.strip(), output.split('\n'))):
        if "Current:" in row:
            current = row[row.find(':')+1:].strip()
            if current == value:
                logger.debug('\tsetParameterByValue() notice: ' + setting + ' is already set to ' + str(current))
                return True
    
    # pass command to change setting to new change value
    set_setting_cmd = ['gphoto2', '--set-config-value', setting + '=' + str(value)]
    output = subprocess.run(set_setting_cmd, stdout=subprocess.PIPE).stdout.decode('utf-8')
    output_lines = list(map(lambda x: x.strip(), output.split('\n')))
    if len(output_lines) == 1:
        #logger.debug('No error output from aperture set command.')
        # assume command was successful if no output; verify in subsequent step
        pass
    else:
        logger.debug('Failed to set new parameter value: see output from gphoto2 command below')
        for line in output_lines:
            logger.debug(line)
        return False
    
    # run syscommand to check value and verify change; return
    output = subprocess.run(get_setting_cmd, stdout=subprocess.PIPE).stdout.decode('utf-8')
    for row in list(map(lambda x: x.strip(), output.split('\n'))):
        if "Current:" in row:
            current = row[row.find(':')+1:].strip()
            if current == value:
                logger.debug('\t' + setting + ' parameter successfully set to ' + str(value))
                return True
            else:
                logger.debug('WARNING: Failed to change value to' + str(value) + ', reason unknown')
                return False
    
    # should be unreachable
    return False

def singleCapture(logger, wait_time, exposure_time, aperture='2.8', iso='Auto', subject_name='AnonymousSubject', timestamp=None, lights='off'):
    '''Capture a single image. Return true iff successful.
    
    Both the exposure_time and wait_time values are interpreted as being in
    seconds. However, because gphoto2 does not appear to correctly intepret
    decimal values for seconds, I specify all times in milliseconds (which
    requires only specifying the unit along with the argument).
    
    Name of the output image file is populated with metadata from the capture
    configuration. An assigned 'light' or 'dark' tag, based on an exposure_time
    cutoff of less <=5 seconds is also included.
    '''
    
    # if using the lights, turn these on and wait a few seconds for bulb to come up to temp
    if lights == 'on':
        GPIO.output(2, GPIO.HIGH)
        time.sleep(3) # time for bulb to come up to tent
    
    # name the target image
    if timestamp == None:
        ts = time.time()
        timestamp = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime(ts))
    if float(exposure_time) >= 5:
        tag = '_dark'
    else:
        tag = '_light'
    image_name = subject_name + '_' + timestamp + tag + '_exp' + str(exposure_time) + 's_' + '_f' + aperture + '_iso' + iso
    
    logger.debug('\tStarting capture routine for ' + image_name + '...')
    
    # program selected capture settings
    logger.debug('\tProgramming capture settings...')
    if not(setParameterByValue(logger, 'aperture', aperture)):
        logger.debug('Failed to set selected aperture! Premature exit of singleCapture() function.')
        return False
    if not (setParameterByValue(logger, 'iso', iso)):
        logger.debug('Failed to set selected iso! Premature exit of singleCapture() function.')
        return False
    logger.debug('\t...done.')
    
    # generate capture command for gphoto2 and pass to system
    wait_time = int(float(wait_time) * 1000) # convert to milliseconds
    exposure_time = int(float(exposure_time) * 1000) # convert to milliseconds
    capture_cmd = ['gphoto2',
                        '--filename', image_name + '.jpg',
                        '--set-config-index', 'eosremoterelease=5',
                        '--wait-event=' + str(exposure_time) + 'ms',
                        '--set-config-index','eosremoterelease=4',
                        '--wait-event-and-download=' + str(wait_time) + 'ms']
    logger.debug('\tpassing capture command...')
    output = subprocess.run(capture_cmd, stdout=subprocess.PIPE).stdout.decode('utf-8')
    logger.debug('\t...done.')
    
    # verify image capture
    '''The gphoto2 output for any bulb exposure is quite verbose... would be
    nice to code a parse check for suppression unless an error is apparent. For
    now, checking for the image file after capture command is complete will
    suffice for QC.
    ''' 
    #for row in list(map(lambda x: x.strip(), output.split('\n'))):
    #    logger.debug(row)
    
    if image_name + '.jpg' in os.listdir():
        logger.debug('\tImage captured!')
        return True
    else:
        logger.debug('WARNING: image capture failed, no image found. Troubleshoot me!')
        return False
    
    # should be unreachable
    return False

def seriesCapture(logger, interval, duration, cycles, wait_time, exposure_time, aperture='2.8', iso='Auto', subject_name='AnonymousSubject', lights='off'):
    '''Run loop for timelapse capture of still images
    
    NOTE: consider implementing argument checking for permissible values of
    exposure times and interval lengths.
    '''
    
    for i in range(0, cycles):
             
        logger.debug('Cycle ' + str(i+1) + ' of ' + str(cycles))
              
        '''Generate timestamp for naming image'''
        ts = time.time() # get timestamp for picture
        timestamp = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime(ts))
        
        ''' Call single capture function '''
        call_time = time.time()
        logger.debug('\tCapture function call: ' + str(call_time))
        singleCapture(logger, wait_time, exposure_time,  aperture=aperture, iso=iso, subject_name=subject_name, timestamp=timestamp, lights=lights)
        return_time = time.time() 
        logger.debug('\tCapture function return: ' + str(return_time))
        logger.debug('\tPicture captured, timestamped ' + timestamp)
        
        ''' Sleep remainder of interval '''
        sleep_interval = interval - (return_time - call_time)
        logger.debug('\tSleeping for ' + str(sleep_interval))
        time.sleep(sleep_interval)
    
    return

def dualSeriesCapture(logger, interval, duration, cycles, wait_time, exposure_time_light, exposure_time_dark, 
                  aperture_light='7.1', aperture_dark='2.8', iso_light='Auto', iso_dark='Auto', subject_name='AnonymousSubject'):
    '''Run loop for timelapse capture of still images, taking first an
    unilluminated "dark" image and then a light image at the beginning and end,
    respectively, of each cycle in the timecourse.
    
    NOTE: The light picture is taken at the very end of the cycle, so that the
    bulb has time to "come up to temp" in terms of the K value (which is highly
    variable when imaging right after turning on the power, unless one buys a
    more fancy bulb). 
    
    NOTE: same implementation for argument safety check would be useful here.
    '''
        
    for i in range(0, cycles):
             
        logger.debug('Cycle ' + str(i+1) + ' of ' + str(cycles))
              
        '''Turn off lights to do the dark exposure first'''
        GPIO.output(2, GPIO.LOW)
        #logger.debug('Lights off!')
        
        '''Generate timestamp for naming image'''
        call_time = time.time() # get timestamp for picture
        timestamp = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime(call_time))
        logger.debug('\tDark capture function call: ' + str(call_time))
        singleCapture(logger, wait_time, exposure_time_dark, aperture_dark, iso_dark, subject_name, timestamp)
        return_time = time.time() 
        logger.debug('\tDark capture function return: ' + str(return_time))
        #logger.debug('\tPicture captured, timestamped ' + timestamp)
        
        GPIO.output(2, GPIO.HIGH)
        #logger.debug('Lights on!')
        
        sleep_interval = interval - (return_time - call_time)
        logger.debug('\tSleeping for ' + str(sleep_interval))
        time.sleep(sleep_interval-2) # wait until almost the very end of the cycle
    
        success = singleCapture(logger, wait_time, exposure_time_light, aperture_light, iso_light, subject_name, timestamp)
        if not success:
            logger.debug('Capture failed!!! Abort abort!!!')
            return
        
        # this is to provide a brief buffer before the "light power off" command
        # is supplied from the next round of the cycle
        time.sleep(2)
        
    return

def runCloseoutOps(logger):
    '''Closeout operations'''
    logger.debug('Setting pin 2 voltage to low...')
    GPIO.output(2, GPIO.LOW) # make sure turned off prior to closing
    #GPIO.cleanup() # reset any previous settings
    logger.debug('...done.')
    return

if __name__ == "__main__":
    
    '''Set up logger routing to console and to file'''
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())
    logger.addHandler(logging.FileHandler('gphoto_capture_control.log', mode='w'))
    logger.debug('gPhoto2 wrapper utility launched!')
   
    proceed = True # script procedural stop-check value
     
    '''Set up relay control via GPIO, with power off'''
    if proceed:
        proceed = initRelayControl(logger)
     
    '''Kill background process that locks camera control '''
    if proceed:
        killMonitorProcess(logger)
     
    ''' Verify that camera is visible to gPhoto2 and set to bulb mode '''
    if proceed:
        proceed = verifyCameraConnect(logger)
    if proceed:
        proceed = verifyBulbMode(logger)
         
    ''' Specify the capture profile '''
    capture_profile = 'dual_series'
      
    ''' Read config file for command and parse universal config options'''
    conf_filename = capture_profile + '.conf'
    conf = readConfFile(conf_filename, capture_profile)
    subject_name = conf['subject']
    # Wait time for the camera prior to pulling the image for download. I
    # originally used 2 seconds per examples I saw online, and this worked fine
    # until I found a bug whereby for very long exposures (>10m), the camera
    # call would return with no error but no image would be downloaded. I
    # hypothesize this is because longer exposure images are larger, and that 2s
    # was insufficient for the data to transfer from the camera to the Pi (or
    # from camera RAM to storage, or whatever data transfer occurs therein).
    wait_time = 10 # in seconds
      
    ''' Call appropriate capture function '''
    if capture_profile == 'single':

        '''Run singleCapture function'''
        singleCapture(logger, wait_time, conf['shutterspeed'], conf['aperture'], conf['iso'], subject_name, None, conf['lights'])
    
    elif capture_profile == 'series' or capture_profile == 'dual_series':
        
        '''Set configs common for timelapse capture functions, and by default
        place images in a new, named subdirectory.'''
        interval = float(conf['interval']) # interval between exposures, in minutes
        duration = float(conf['duration']) # total duration for time-lapse, in hours
        interval = interval * 60 # convert to seconds
        duration = duration * 3600 # convert to seconds  
        cycles = int(duration / (interval))        
        
        os.chdir('images') # move into images folder before create a subdirectory
        ts = time.time()
        batchname = subject_name + '_' + time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime(ts)) 
        logger.debug('Starting new batch picture cycle: ' + batchname)
        subprocess.call('mkdir ' + batchname, shell=True)
        os.chdir(batchname) # move into the new subdirectory  
        
        if capture_profile == 'series':
            
            '''Run seriesCapture function with fixed lighting'''     
            exposure_time = conf['shutterspeed'] # in seconds; left verbose for convenient unit conversion
            logger.debug('Initiating timelapse loop: ' + str(cycles) + ' cycles with ' + str(interval) + 's intervals')
            seriesCapture(logger, interval, duration, cycles, wait_time, exposure_time, conf['aperture'],conf['iso'], subject_name, conf['lights'])
            logger.debug('Picture cycle ended')
            
        else:
             
            '''Run seriesCapture function with lights control, interleaved light and
            dark images.'''
            exposure_time_light = conf['shutterspeed_light'] # in seconds
            exposure_time_dark =conf['shutterspeed_dark'] # in seconds
            logger.debug('Initiating timelapse loop: ' + str(cycles) + ' cycles with ' + str(interval) + 's intervals')
            dualSeriesCapture(logger, interval, duration, cycles, wait_time, exposure_time_light, exposure_time_dark, 
                          aperture_light=conf['aperture_light'], aperture_dark=conf['aperture_dark'], 
                          iso_light=conf['iso_light'], iso_dark=conf['iso_dark'], 
                          subject_name=subject_name)
            logger.debug('Picture cycle ended')
            
    else:
        
        logger.debug('capture_profile not recognized')
    
    ''' Run any cleanup operations (i.e. reset relay) '''
    runCloseoutOps(logger)
    
    
    
    
    
    
    
