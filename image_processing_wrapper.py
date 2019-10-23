'''
Wrapper script for automation of image processing steps using ImageJ and FFMPEG.

Author: James Chamness
Version: 1.0 (October 6, 2019)

'''
import os
import re
import subprocess
import time

def callBatchMacro(ij_jar_path, input_dir, output_dir, macro_path, macro_name):
    '''Call a single ImageJ macro
    
    Calls a specific named ImageJ macro function stored in the macro file at the
    given path. These are all intended to be batch operations - in the macros
    file, whichever named function is called is applied across all the images in
    the input folder (and output images saved to the output folder). 
    '''
    # imageJ is not smart about recognizing paths
    if not input_dir[-1] == os.sep:
        input_dir = input_dir + os.sep
    if not output_dir[-1] == os.sep:
        output_dir = output_dir + os.sep
    
    call_cmd = ['java',
               '-jar',
               ij_jar_path,
               '-macro',
               macro_path,
               macro_name + "#" + 
               input_dir + "#" + output_dir
               ]
    output = subprocess.run(call_cmd, stdout=subprocess.PIPE).stdout.decode('utf-8')
    return

def timestampImageFolder(imageFolderPath):
    '''Add name-extracted timestamps as watermarks across a directory of images.
    
    NOTE: figure out how to place text in corner with fixed buffer distance; there's
    a slight bit of horizontal jitter, regarding placement, between frames, due to
    variable width of the watermark text. Idea: could use reference to text height
    instead of width (th instead of tw), since this is less likely to vary. or do in
    a monospace font?
    
    NOTE: could add a counter, useful for tracking progress over long batches
    
    NOTE: probably actually more efficient to move this step into ImageJ pipeline
    '''
    
    # move into target directory to perform operations
    old_dir = os.getcwd()
    os.chdir(imageFolderPath)
    orderedImages = sorted([x for x in os.listdir()])
    
    # apply operation to all the image files
    frameCounter = 0 # FFMPEG expects frame numbering to start at 0 (used later)
    for x in orderedImages:
        # use regex for parsing is the simplest thing since date has fixed format
        #timestamp_expression = re.compile(r'\d\d\d\d-\d\d-\d\d_\d\d:\d\d:\d\d') # entire timestamp
        timestamp_expression = re.compile(r'\d\d:\d\d:\d\d') # just the time, not the date
        timestamp = timestamp_expression.search(x).group(0)
        timestamp = timestamp.replace(':','\:') # necessary so that standard colon doesn't break ffmpeg option parsing
        cmdStr = 'ffmpeg -i ' + x + ' -vf "drawtext=text=' + "'" + timestamp + "'" + ':fontcolor=white:fontsize=140:x=w-tw-(tw/8):y=th+(th/8)" frame-' + str(frameCounter) + '.jpg'
        subprocess.call(cmdStr, shell=True)
        frameCounter += 1
     
    os.chdir(old_dir)
    return

def makeVideo(imageFolderPath, inputFPS):
    '''Make video from a single set of frames.'''
    
    olddir = os.getcwd()
    os.chdir(imageFolderPath)
    subject_name = imageFolderPath[imageFolderPath.rfind(os.sep)+1:]
    name = subject_name + '.avi'
    cmdstr = 'ffmpeg -framerate ' + str(inputFPS) + ' -i frame-%d.jpg -r 30 ' + name
    subprocess.call(cmdstr, shell=True)

    # clean up all the intermediate files (watermarked frames)
    cmdstr = 'rm frame-*'
    subprocess.call(cmdstr, shell=True)
    
    os.chdir(olddir)
    return

if __name__ == "__main__":
    
    ''' Specify configurable parameters '''
    #subject_name = 'SV1_Drought_responsive'
    #macro_name = 'sv1'
    subject_name = 'SV2_Recycling_comparison'
    macro_name = 'sv2'
     
    image_dir = '/home/james/Code/P4/images/raw/' + subject_name
     
      
    ''' Parse list of matching filenames for original images '''
    os.chdir(image_dir)
    image_files = []
    for x in os.listdir():
        if not os.path.isdir(x) and x[:len(subject_name)] == subject_name:
            image_files.append(x)
        
    ''' Create output directory for processed images '''
    os.chdir('../../processed')
    cmd = 'mkdir -p ' + subject_name
    subprocess.call(cmd, shell=True)
    os.chdir(subject_name)
    output_dir = os.getcwd()
        
    ''' Call ImageJ macro(s) '''
    ij_jar_path = '/usr/local/ImageJ/ij.jar'
    macros_path = '/home/james/Code/P4/batch_macros.ijm'
    start = time.time()
    callBatchMacro(ij_jar_path, image_dir, output_dir, macros_path, macro_name)
    end = time.time()
    #print(end-start)
       
    ''' Extract timestamps from image filenames and add to images '''
    timestampImageFolder(output_dir)
      
    ''' Concatenate frames into a video file '''
    makeVideo(output_dir, 4)
    
    #import os
    #os.chdir("/home/james/Code/P4/images/raw/SV2_Recycling_comparison")
    #[os.rename(f, f.replace('RecyclingComparison', 'SV2_Recycling_comparison')) for f in os.listdir('.') if not f.startswith('.')]
    
    print("\nDone!")
    