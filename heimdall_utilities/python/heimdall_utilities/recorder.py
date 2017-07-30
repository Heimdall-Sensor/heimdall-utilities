#!/usr/bin/env python

#
#  Heimdall Utilities - Utilities to work on Heimdall
#  Copyright (C) 2017 Christof Oost, Amir Shantia, Ron Snijders, Egbert van der Wal
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of the
#  License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
import rospy

from threading import Lock
import subprocess
import pickle
import signal
import time
import sys
import rospy
import cv2
from std_msgs.msg import String
from std_msgs.msg import Int64
from sensor_msgs.msg import Image
from cv_bridge import CvBridge, CvBridgeError
import numpy as np

recorder = None

class ExperimentRecorder:
    """
    Recorder used to create a recording of the experiments.
    Subscribes to these image topics, and merged them together:
    - /rita/pov/image
    - /simcam/topdown/image_raw
    - /simcam/side/image_raw
    - /clf_visualizer/image
    To record:
    rosrun rs_exp recorder.py --record
    To prepare the movie with a desired framerate:
    rosrun rs_exp recorder.py --prepare-movie <framerate>
    To create the actual movie with a desired framerate.
    rosrun rs_exp recorder.py --create-movie <framerate>
    By default, all frames will be saved to /ramfs.
    """

    def __init__(self):
        self._lock = Lock()
        self._bridge = CvBridge()
        #Vars related to processing:
        self._last_process_time = self.time()
        self._frame_idx = 0
        #self._max_freq = 15.0
        self._time_list = []
        self._failure_time_list = []
        #Image topics to record:
        self._image_topic_dict = {
            "rgb":"/camera/rgb/image_raw",
        }
        self._image_sub_dict = {}
        #Create image subscribers: 
        for image_key, image_topic in self._image_topic_dict.iteritems():
            self._image_sub_dict[image_key] = {"last_image":None, "last_time":self.time(), "topic":image_topic}
            self._image_sub_dict[image_key]["sub"] = rospy.Subscriber(image_topic, Image, self.image_cb, callback_args = image_key)
        self._last_freq_calc_time = self.time()
        self._last_freq_frame_idx = 0

    def time(self):
        return time.clock()

    def image_cb(self, data, image_topic):
        """
        Global image call back function.
        @param image_topic  The custom provided topic name of the image.
        """
        cv_image = self._bridge.imgmsg_to_cv2(data, "bgr8")
        (height, width, channels) = cv_image.shape
        assert height == 240
        assert width == 320
        self._lock.acquire()
        self._image_sub_dict[image_topic]["last_image"] = cv_image
        self._image_sub_dict[image_topic]["last_time"] = self.time()
        self.process()
        self._lock.release()

    def get_newest_image_time(self):
        """
        Returns the most recent image time of all requested imag topics.
        """
        time = 0.0
        for image_sub in self._image_sub_dict.itervalues():
            if image_sub["last_time"] > time:
                time = image_sub["last_time"]
        return time

    def get_oldest_image_time(self):
        """
        Returns the oldest image time of all requested imag topics.
        """
        time = None
        for image_sub in self._image_sub_dict.itervalues():
            if time == None or image_sub["last_time"] < time:
                time = image_sub["last_time"]
        return time

    def have_all_images(self):
        """
        Returns True if at least 1 image per topic has been received, False otherwise.
        """
        for image_sub in self._image_sub_dict.itervalues():
            if image_sub["last_image"] == None:
                return False
        return True

    def process(self):
        """
        Called after receiving a single image.
        Creates a new merged frame of a image topics.
        """
        #All images received ?
        #At least 1 image per topic received? And new since last processing?
        cur_time = self.time()
        if self.have_all_images(): 
            newest_time = self.get_newest_image_time()
            if newest_time > self._last_process_time:
                #print "Processing frame %d" % self._frame_idx
                frame = self._image_sub_dict["rgb"]["last_image"]
                #Stitch images all together:
                #Join simcams horizontally:
                #simcams = np.concatenate((self._image_sub_dict["simcam_topdown"]["last_image"], self._image_sub_dict["simcam_side"]["last_image"]), axis = 0)
                #Join Rgb camera and clf visualizer horizontally:
                #rita = np.concatenate((self._image_sub_dict["rgb"]["last_image"], self._image_sub_dict["clf_visualizer"]["last_image"]), axis = 0)
                #Join vertically:
                #frame = np.concatenate((rita, simcams), axis = 1)
                
                cv2.imwrite("/ramfs/%07d.png" % self._frame_idx, frame)
                #print cur_time
                self._time_list.append(cur_time)
                #Indicate processed frame:
                self._frame_idx += 1
                self._last_process_time = self.time()
        else:
            print "not ok all received!"

    def save(self):
        """
        Saves the timestamp of each frame required to create the movie.
        """
        print "Saving..."
        assert len(self._time_list) == self._frame_idx 
        pickle.dump(self._time_list, open("timelist.data", "wb"))
        pickle.dump(self._failure_time_list, open("failuretimelist.data", "wb"))

def signal_handler(signal, frame):
    """
    Catches Ctrl+C signal and saves timestamp data.
    """
    global recorder
    print('You pressed Ctrl+C!')
    recorder.save()
    sys.exit(0)

if __name__ == "__main__":
    global recorder
    signal.signal(signal.SIGINT, signal_handler)

    command = "--record"
    if len(sys.argv) > 1:
        command = sys.argv[1]

    if command == "--record":
        rospy.init_node('experiment_recorder')
        recorder = ExperimentRecorder()
        rospy.spin()
    elif command == "--prepare-movie":
        framerate = 5
        if len(sys.argv) > 2:
            framerate = int(sys.argv[2])
        time_list = pickle.load(open("timelist.data", "rb"))
        #Create frames (and interpolate frames (if nessary)):
        cur_time = time_list[0]
        frame_idx = 0
        new_frame_idx = 0
        while True:
            #Consumed all?
            if (frame_idx + 1) >= len(time_list):
                break
            #Get newest frame within cur_time:
            while True:
                #Consumed all?
                if (frame_idx + 1) >= len(time_list):
                    break
                if time_list[frame_idx + 1] < cur_time:
                    frame_idx += 1
                else:
                    break
            #Create new frame:
            print "frame: %d" % new_frame_idx
            subprocess.call(["cp", "./%07d.png" % frame_idx, "./movie/%07d.png" % new_frame_idx])
            new_frame_idx += 1
            cur_time += 1.0 / framerate
    elif command == "--create-movie":
        framerate = 5
        if len(sys.argv) > 2:
            framerate = int(sys.argv[2])
        cmd = "mencoder mf://movie/*.png -mf fps=%d:type=png -ovc x264 -x264encopts bitrate=12000:threads=2 -o outputfile.mkv" % framerate
        cmd_list = cmd.split(" ")
        subprocess.call(cmd_list)
    else:
        raise RuntimeError("Unknown command: %s" % command)

#To create movie:
#
