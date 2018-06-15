# MUltimodal Recording

# Erik Strahl
# Matthias Kerzel
# Stefan Heinrich

# GNU GPL License


from nicomotion import Motion
from nicomotion import Mover
import pypot.dynamixel
from time import sleep
import datetime
from nicotouch.optoforcesensors import optoforce
import logging
from nicovision import ImageRecorder
import os
from os.path import dirname, abspath
from time import sleep
import datetime
import sys
import cv2
from nicoaudio import pulse_audio_recorder
from subprocess import call
import sqlite3
import random
from subprocess import call
import matplotlib.pyplot as plt
from scipy.io import wavfile
import numpy as np


fnl = "left_cam_synced_data"
fnr = "right_cam_synced_data"
fpostfix = ".csv"
robot = None

import shutil

# experiment definitions (Objects and number of graspings)
# definition of objects
# objects =["blue ball","blue_plush ball","red_plush ball", "orange_plush ball", \
#          "white cube", "big_yellow die", "medium_yellow die","small_yellow die", \
#          "yellow sponge", "green sponge","blue tissues","pink tissues", \
#          "yellow apple", "light_green apple","heavy_green apple", "realistic_green apple", \
#          "red car","blue car","yellow car", "green car", \
#          "light tomato", "heavy tomato","small_red ball", "large_red ball", \
#          "small banana", "plush banana", "heavy banana","aubergine banana", \
#          "yellow duck","purple duck","orange fish","yellow seal"]

# Test objects for Marcel
objects = ["blue ball", "blue_plush ball", "red_plush ball", "orange_plush ball",
           "big_yellow die", "small_yellow die", "yellow car", "green apple",
           "light tomato", "heavy tomato", "red ball", "red apple"]

# definition of the actions
# name of the action : [wait time for reaching the position]
# the number of wait times defines as well the position steps to go
# the position steps are defined in files named pos_[actionname]_[no of step].csv

actions = {
    "pull": [1.5, 2, 4, 2, 1.5],
    "push": [1, 1, 1, 1]
}

# action="pull"

# data_directory
data_directory = "/data2/20180615_multimodal_recording_with_integrity_checks"

# definition for numbers per object
number_of_samples_per_object = 10

# definition of Maximum current - This protects the hands from breaking!! Do not change this, if you do not know!
MAX_CUR_FINGER = 120
MAX_CUR_THUMB = 100

# Data for SQlite Access
# Experiment Data will be stored in two table database
# with samples for every sample of a grasped onject and subsample for every motor step (like for 10 degrees)

print "database file: " + data_directory+"/multimodal_experiment.db"

connection = sqlite3.connect(data_directory+"/multimodal_experiment.db")


cursor = connection.cursor()
# status: 0-succesful , 1- overload, 2 - former_overload


format_str_sample = """INSERT INTO sample (sample_number,object_name , action, timecode)
    VALUES (NULL, "{object_name}", "{action}","{timecode}");"""


# Data for robot movement in high level mode
# move joints with 10 per cent of the speed and hand joints with full speed
fMS = 0.01
fMS_hand = 1.0


# Pandas structures for storing joint data
import pandas as pd
columns = ["r_shoulder_z_pos", "r_shoulder_y_pos", "r_arm_x_pos", "r_elbow_y_pos", "r_wrist_z_pos", "r_wrist_x_pos", "r_indexfingers_x_pos", "r_thumb_x_pos", "head_z_pos", "head_y_pos",
           "r_shoulder_z_cur", "r_shoulder_y_cur", "r_arm_x_cur", "r_elbow_y_cur", "r_wrist_z_cur", "r_wrist_x_cur", "r_indexfingers_x_cur", "r_thumb_x_cur", "head_z_cur", "head_y_cur",
           "isotime", "touch_isotime", "touch_count", "touch_x", "touch_y", "touch_z"]
dfl = pd.DataFrame(columns=columns)
dfr = pd.DataFrame(columns=columns)

# For accessing the json structure:
sm_proprioception = ["r_shoulder_z", "r_shoulder_y", "r_arm_x", "r_elbow_y",
                     "r_wrist_z", "r_wrist_x", "r_indexfingers_x", "r_thumb_x", "head_z", "head_y"]
sm_tactile = ["touch_x", "touch_y", "touch_z"]


def write_joint_data(robot, df, iso_time):

    # df = pd.DataFrame.append(data={"r_arm_x":[robot.getAngle("r_arm_x")],"r_elbow_y":[robot.getAngle("r_elbow_y")],"head_z":[robot.getAngle("head_z")],"isotime":[iso_time]})
    (stime, counter, status, x, y, z, checksum) = optoforce_sensor.get_sensor_all()
    dfn = pd.DataFrame(data={"r_shoulder_z_pos": [robot.getAngle("r_shoulder_z")],
                             "r_shoulder_y_pos": [robot.getAngle("r_shoulder_y")],
                             "r_arm_x_pos": [robot.getAngle("r_arm_x")],
                             "r_elbow_y_pos": [robot.getAngle("r_elbow_y")],
                             "r_wrist_z_pos": [robot.getAngle("r_wrist_z")],
                             "r_wrist_x_pos": [robot.getAngle("r_wrist_x")],
                             "r_indexfingers_x_pos": [robot.getAngle("r_indexfingers_x")],
                             "r_thumb_x_pos": [robot.getAngle("r_thumb_x")],
                             "head_z_pos": [robot.getAngle("head_z")],
                             "head_y_pos": [robot.getAngle("head_z")],
                             "r_shoulder_z_cur": [robot.getCurrent("r_shoulder_z")],
                             "r_shoulder_y_cur": [robot.getCurrent("r_shoulder_y")],
                             "r_arm_x_cur": [robot.getCurrent("r_arm_x")],
                             "r_elbow_y_cur": [robot.getCurrent("r_elbow_y")],
                             "r_wrist_z_cur": [robot.getCurrent("r_wrist_z")],
                             "r_wrist_x_cur": [robot.getCurrent("r_wrist_x")],
                             "r_indexfingers_x_cur": [robot.getCurrent("r_indexfingers_x")],
                             "r_thumb_x_cur": [robot.getCurrent("r_thumb_x")],
                             "head_z_cur": [robot.getCurrent("head_z")],
                             "head_y_cur": [robot.getCurrent("head_z")],
                             "isotime": [iso_time],
                             "touch_isotime": [stime],
                             "touch_count": [counter],
                             "touch_x": [x],
                             "touch_y": [y],
                             "touch_z": [z]})
    df = pd.concat([df, dfn], ignore_index=True)

    # df = pd.DataFrame(data={"r_arm_x":[robot.getAngle("r_arm_x")],"r_elbow_y":[robot.getAngle("r_elbow_y")],"head_z":[robot.getAngle("head_z")]})
    return(df)


class leftcam_ImageRecorder(ImageRecorder.ImageRecorder):

    def custom_callback(self, iso_time, frame):

        global dfl

        # write joint data

        dfl = write_joint_data(robot, dfl, iso_time)

        # small = cv2.resize(frame, (0,0), fx=0.5, fy=0.5)
        # small=cv2.flip(small,-1)
        # return(small)
        return(frame)


class rightcam_ImageRecorder(ImageRecorder.ImageRecorder):

    def custom_callback(self, iso_time, frame):

        global dfr

        # write joint data

        dfr = write_joint_data(robot, dfr, iso_time)

        # small = cv2.resize(frame, (0,0), fx=0.5, fy=0.5)
        # return(small)
        return(frame)


def get_sampled_numbers_for_object(object_name, action):

    sql = "SELECT * FROM sample where object_name='" + \
        object_name + "' and action='"+action+"';"
    cursor.execute(sql)
    result = cursor.fetchall()
    return len(result)


def get_needed_numbers_for_object(object_name, action):

    num = number_of_samples_per_object - \
        get_sampled_numbers_for_object(object_name, action)
    return (num)


def get_needed_overall_numbers():
    sum = 0
    for action in actions.keys():
        for o in objects:
            sum += get_needed_numbers_for_object(o, action)
    return(sum)


def print_progress():
    for action in actions.keys():
        print "\n\nFor action: " + action + "\n"
        for o in objects:
            print " For object " + o + " and action " + action + " - samples needed: " + \
                str(get_needed_numbers_for_object(o, action))
            " - samples finished: " + \
                str(get_sampled_numbers_for_object(o, action))


def normalise_data_sensorimotor(config, sm_proprioception, sm_tactile, dfp):

    dfp_norm = dfp

    for x in sm_proprioception:
        dfp_norm[[str(x) + "_pos"]] = \
            (dfp[[str(x)+"_pos"]].values[:, 0]
             - config["motors"][str(x)]["angle_limit"][0]) \
            / (config["motors"][str(x)]["angle_limit"][1]
               - config["motors"][str(x)]["angle_limit"][0])

    for x in sm_proprioception:
        dfp_norm[[str(x) + "_cur"]] = \
            (dfp[[str(x)+"_cur"]].values[:, 0]
             - config["motors"][str(x)]["current_limit"][0]) \
            / (config["motors"][str(x)]["current_limit"][1]
               - config["motors"][str(x)]["current_limit"][0])

    for x in sm_tactile:
        dfp_norm[[str(x)]] = \
            (dfp[[str(x)]].values[:, 0]
             - config["optoforce"][str(x)]["force_limit"][0]) \
            / (config["optoforce"][str(x)]["force_limit"][1]
               - config["optoforce"][str(x)]["force_limit"][0])

    return dfp_norm


def plot_data_audio(audio_file, plot_audio_file):
    sample_rate, samples = wavfile.read(audio_file)
    samples_mono = 0.5*samples[:, 0] + 0.5*samples[:, 1]

    plt.subplot(211)
    plt.plot(samples_mono)
    plt.ylabel('Amplitude')

    plt.subplot(212)
    plt.specgram(samples_mono, Fs=sample_rate)
    plt.xlabel('Time')
    plt.ylabel('Frequency')

    plt.savefig(plot_audio_file)

    return True


def plot_data_sensorimotor(sm_proprioception, sm_tactile, dfp_norm, plot_file_sm):

    sm_pos_norm = np.array([dfp_norm[[str(x)+"_pos"]].values[:, 0]
                            for x in sm_proprioception])

    sm_cur_norm = np.array([dfp_norm[[str(x)+"_cur"]].values[:, 0]
                            for x in sm_proprioception])

    sm_tactile_norm = np.array(
        [(dfp_norm[[str(x)]].values[:, 0]) for x in sm_tactile])

    plt.subplot(311)
    plt.plot(sm_pos_norm.T)
    plt.ylabel('Position')
    plt.ylim(-0.1, 1.1)

    plt.subplot(312)
    plt.plot(sm_cur_norm.T)
    plt.ylabel('Current')
    plt.ylim(-0.1, 1.1)

    plt.subplot(313)
    plt.plot(sm_tactile_norm.T)
    plt.xlabel('Time')
    plt.ylabel('Touch')
    plt.ylim(-0.1, 1.1)

    plt.savefig(plot_file_sm)

    return True


# Print out was is still needed
# print "objects and actions"
# print str(objects) + " " + str(actions)

print "\n\nWe still need the following samples:"

print_progress()

if get_needed_overall_numbers() > 0:
    print "\n\nOverall there are still " + \
        str(get_needed_overall_numbers()) + " samples needed.\n\n"
else:
    print "\n\nAll samples recorded. Thank you. If you needed more, adapt the number_of_samples_per_object parameter on the programm.\n\n"
    exit(0)


# Instructions for the experimenter. Brig the robot in Initial position
print "\n Please put the robot in position. Right arm on the table. Left arm hanging down. Give RETURN after finished.\n"
raw_input()

# Optoforce_sensor
optoforce_sensor = optoforce(ser_number=None, cache_frequency=40)

# Put the left arm in defined position
robot = Motion.Motion(
    "../../../json/nico_humanoid_legged_minimal_for_multimodal_recordings.json", vrep=False)
mover_path = "../../../moves_and_positions/"
mov = Mover.Mover(robot, stiff_off=False)
robot_config = robot.getConfig()

sleep(4)

# set the robot to be compliant
robot.disableTorqueAll()

robot.openHand('RHand', fractionMaxSpeed=fMS_hand)

robot.enableForceControl("r_wrist_z", 50)
robot.enableForceControl("r_wrist_x", 50)

robot.enableForceControl("r_indexfingers_x", 50)
robot.enableForceControl("r_thumb_x", 50)

# enable torque of left arm joints
robot.enableForceControl("head_z", 20)
robot.enableForceControl("head_y", 20)

robot.enableForceControl("r_shoulder_z", 20)
robot.enableForceControl("r_shoulder_y", 20)
robot.enableForceControl("r_arm_x", 20)
robot.enableForceControl("r_elbow_y", 20)

robot.setAngle("r_thumb_x", 160, 0.4)
robot.setAngle("r_indexfingers_x", -160, 0.4)


# Instructions for the experimenter. Brig the robot in Initial position
print "\n OK. The robot is positioned. We will start the experiment now.\n\n"

pulse_device = pulse_audio_recorder.get_pulse_device()

res_x = 1920
res_y = 1080
framerate = 30
amount_of_cams = 2
logging.getLogger().setLevel(logging.INFO)

# Vision Recording
device = ImageRecorder.get_devices()[0]
ir = leftcam_ImageRecorder(
    device, res_x, res_y, framerate=framerate, writer_threads=3, pixel_format="UYVY")

if amount_of_cams >= 2:
    device2 = ImageRecorder.get_devices()[1]
    ir2 = rightcam_ImageRecorder(
        device2, res_x, res_y, framerate=framerate, writer_threads=3, pixel_format="UYVY")

sleep(2)

# Sound Recording
ar = pulse_audio_recorder.AudioRecorder(
    audio_channels=2, samplerate=48000, datadir="./.", audio_device=pulse_device)


while (get_needed_overall_numbers() > 0):

    # Select an object
    action = random.choice(actions.keys())
    o = random.choice(objects)
    while (get_needed_numbers_for_object(o, action) < 1):
        action = random.choice(actions.keys)
        o = random.choice(objects)

    print "\nRandomly chosen action : " + action + "\n"

    print "Randomly chosen object : " + o + "\n"

    print "\n\n Please put the " + o + \
        " onto the table at the marked position. Then press RETURN."
    raw_input()

    try:
        os.mkdir(data_directory+'/'+action)
    except OSError:
        pass

    dfl = pd.DataFrame(columns=columns)
    dfr = pd.DataFrame(columns=columns)

    #!!!!Write Sample data in database
    sql_command = format_str_sample.format(
        object_name=o, action=action, timecode=datetime.datetime.now().isoformat())
    # print "\n " +sql_command
    cursor.execute(sql_command)
    sample_number = cursor.lastrowid

    str_sample_number = str(sample_number)

    cur_dir = data_directory+'/'+action+'/'+str_sample_number
    # print "dir: " + cur_dir
    # raw_input()

    try:
        os.mkdir(cur_dir)
    except OSError:
        pass

    try:
        os.mkdir(cur_dir+'/camera1')
    except OSError:
        pass

    try:
        os.mkdir(cur_dir+'/camera2')
    except OSError:
        pass

    label = datetime.datetime.today().isoformat()
    # ar.start_recording(label,fname="./"+action+'/'+str_sample_number+label+".wav",dir_name="./audio/")
    ar.start_recording(label, fname=cur_dir+'/'+label+".wav", dir_name="")

    ir.start_recording(cur_dir+'/camera1/picture-{}.png')
    if amount_of_cams >= 2:
        ir2.start_recording(cur_dir+'/camera2/picture-{}.png')

    for n, wait_duration in enumerate(actions[action]):
		print "breaks: " + str(wait_duration)
		mov.move_file_position(mover_path + "pos_pull_"+str(n+1)+".csv",
								subsetfname=mover_path + "subset_right_arm.csv", move_speed=0.05)
		sleep(wait_duration)
    mov.move_file_position(mover_path + "pos_pull_"+str(1)+".csv",
                           subsetfname=mover_path + "subset_right_arm.csv", move_speed=0.05, )
    sleep(10)

    # PULL action:

    # 1) go to start position
    # 2) retract thumb
    # 3)

    # robot.openHand("RHand", fractionMaxSpeed=0.4)
    # sleep(5)
    # robot.closeHand("RHand", fractionMaxSpeed=0.4)
    # sleep(5)
    # robot.openHand("RHand", fractionMaxSpeed=0.4)

    # Stop and finish camera recordings
    ir.stop_recording()
    if amount_of_cams >= 2:
        ir2.stop_recording()

    # Stop and write audio recordings
    ar.stop_recording(0)

    print "\n Checking the data integrity of this sample - please wait a moment"
	data_check_result = data_check_clean(cur_dir, dfl, dfr)

	print "\n Waiting for pictures writing on disk - please wait a moment"
    wait_for_camera_writing(cur_dir+'/camera1/')
    wait_for_camera_writing(cur_dir+'/camera2/')

    answer = "dummy"
    if not data_check_result == "":
        answer = "R"
        print("\n.Sorry. Detected problems with this sample. I have to delete the data. ")
        print ("\n The detected problem is: " + data_check_result)

    while (answer != "R" and answer != ""):
        print ("Has the recording of this sample been succesful or do you want to repeat it ? (R=Repeat) / (Return=Continue) ")
        answer = raw_input()

    # Hint (StH): we can use/extend the plot methods also for plotting within an opencv windows

    if answer == "":
        # Write joint data to file
        for df_set in ((fnl, dfl), (fnr, dfr)):
            fn, dfp = df_set
            fnp = cur_dir + "/" + fn + fpostfix
            fnpnorm = cur_dir + "/" + fn + "_norm" + fpostfix
            fnplot = cur_dir + fn + "_norm" + ".svg"
            with open(fnp, 'a') as f:
                dfp.to_csv(f, header=True)

            # Write joint data to file
            dfp_norm = normalise_data_sensorimotor(robot_config, sm_proprioception,
                                                   sm_tactile, dfp)
            with open(fnpnorm, 'a') as f:
                dfp_norm.to_csv(f, header=True)

            # Plot sensorimotor data:
            plot_data_sensorimotor(sm_proprioception, sm_tactile, dfp_norm,
                                   fnplot)

        # Plot audio data:
        plot_data_audio(cur_dir + '/' + label + ".wav",
                        cur_dir + '/' + label + "_audio.svg")

        # commit the database changes
        connection.commit()
    else:
        call(["rm", "-rf", cur_dir])

        # rollback the database changes
        connection.rollback()


connection.close()
print "\n\n Great! I got all samples together! Finishing experiment.\n"
print_progress()

robot = None

# set the robot to be compliant
