import json
import logging
import threading
import time
from math import ceil
from os.path import abspath, dirname, isfile

import cv2
import numpy as np

import Barrier
import MultiCamRecorder
from NumpyEncoder import NumpyEncoder


def takespread(sequence, num):
    length = float(len(sequence))
    r = []
    for i in range(num):
        r.append(sequence[int(ceil(i * length / num))])
    return r


class CameraCalibrator():
    """docstring for CameraCalibrator."""

    def __init__(self, devices=[], width=640, height=480, framerate=20,
                 zoom=None, pan=None, tilt=None, settings_file=None,
                 setting="standard", pixel_format="MJPG"):
        self._dim = width, height
        self._recorder = MultiCamRecorder.MultiCamRecorder(devices, width,
                                                           height, framerate,
                                                           zoom, pan, tilt,
                                                           settings_file,
                                                           setting, 0,
                                                           pixel_format)
        self._deviceIds = self._recorder._deviceIds
        self._current_frames = [
            np.zeros((height, width, 3), np.uint8)] * len(self._deviceIds)
        self._stop_event = threading.Event()
        self._display = threading.Thread(
            target=self._display_thread, args=(self._stop_event,))
        self._display.daemon = True
        self._display.start()

    def __del__(self):
        cv2.destroyAllWindows()

    def _display_thread(self, stop_event):
        while not stop_event.is_set():
            cv2.imshow("cameras", cv2.hconcat(self._current_frames))
            cv2.waitKey(1)

    def _callback(self, rval, frame, id):
        if (rval):
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Find the chess board corners
            self._rvals[id], corners = cv2.findChessboardCorners(
                gray, self._chessboard, cv2.CALIB_CB_ADAPTIVE_THRESH +
                cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE)

            try:
                self._chess_detection_barrier.wait()
            except Barrier.BrokenBarrierError:
                return
            # If found, add object points, image points (after refining them)
            if reduce(lambda x, y: x and y, self._rvals) is True:

                corners2 = cv2.cornerSubPix(
                    gray, corners, (3, 3), (-1, -1), self._criteria)
                self._imgpoints[id].append(corners2)

                # Draw and display the corners
                self._current_frames[id] = cv2.drawChessboardCorners(
                    frame, self._chessboard, corners2, self._rvals[id])
            else:
                self._current_frames[id] = frame

    def _calibrate_mono(self, id):
        """
        Generates calibration parameters from image points recorded with the
        device at the given index in device ids (NOT the actual device id)
        :param id: position of device in list of deviceIds
                   (NOT the actual device id)
        :type id: int
        """
        if self._imgpoints[id] is None or not self._imgpoints[id]:
            logging.warning("Unable to calibrate device " +
                            self._deviceIds[id] + " - no imagepoints recorded")
            return None

        logging.info("Calibrating device {}".format(self._deviceIds[id]))

        # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
        objp = np.zeros(
            (self._chessboard[0] * self._chessboard[1], 1, 3), np.float64)
        objp[:, 0, :2] = np.mgrid[0:self._chessboard[0],
                                  0:self._chessboard[1]].T.reshape(-1, 2)

        objpoints = np.array(
            [objp] * len(self._imgpoints[id]), dtype=np.float64)

        N_OK = len(objpoints)
        K = np.zeros((3, 3))
        D = np.zeros((4, 1))
        rvecs = [np.zeros((1, 1, 3), dtype=np.float64) for i in range(N_OK)]
        tvecs = [np.zeros((1, 1, 3), dtype=np.float64) for i in range(N_OK)]
        ret, K, D, rvecs, tvecs = \
            cv2.fisheye.calibrate(
                objpoints,
                self._imgpoints[id],
                self._dim,
                K,
                D,
                rvecs,
                tvecs,
                self._calibration_flags,
                (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-6)
            )

        return dict((("K", K), ("D", D)))

    def _calibrate_stereo(self):
        """
        Generates calibration parameters from image points recorded with
        stereo cameras
        """
        if len(self._imgpoints) != 2:
            logging.error("Stereo calibration requires exactly 2 devices")
            return None
        if None in self._imgpoints or [] in self._imgpoints:
            logging.warning("Unable to calibrate stereo device " +
                            "- no imagepoints recorded")
            return None

        logging.info("Calibrating stereo camera")
        N_OK = len(self._imgpoints[0])
        K_left = np.zeros((3, 3))
        D_left = np.zeros((4, 1))
        K_right = np.zeros((3, 3))
        D_right = np.zeros((4, 1))
        R = np.zeros((1, 1, 3), dtype=np.float64)
        T = np.zeros((1, 1, 3), dtype=np.float64)

        # prepare object points, like (0,0,0), (1,0,0), (2,0,0) ....,(6,5,0)
        objp = np.zeros(
            (self._chessboard[0] * self._chessboard[1], 1, 3), np.float64)
        objp[:, 0, :2] = np.mgrid[0:self._chessboard[0],
                                  0:self._chessboard[1]].T.reshape(-1, 2)

        objpoints = np.array(
            [objp] * len(self._imgpoints[0]), dtype=np.float64)
        imgpoints_left = np.asarray(self._imgpoints[0], dtype=np.float64)
        imgpoints_right = np.asarray(self._imgpoints[1], dtype=np.float64)

        objpoints = np.reshape(
            objpoints, (N_OK, 1, self._chessboard[0] * self._chessboard[1], 3))
        imgpoints_left = np.reshape(
            imgpoints_left,
            (N_OK, 1, self._chessboard[0] * self._chessboard[1], 2))
        imgpoints_right = np.reshape(
            imgpoints_right,
            (N_OK, 1, self._chessboard[0] * self._chessboard[1], 2))

        ret, K_left, D_left, K_right, D_right, R, T = \
            cv2.fisheye.stereoCalibrate(
                objpoints,
                imgpoints_left,
                imgpoints_right,
                K_left,
                D_left,
                K_right,
                D_right,
                self._dim,
                R,
                T,
                self._calibration_flags,
                (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 1e-6)
            )

        R_left, R_right, P_left, P_right, Q = cv2.fisheye.stereoRectify(
            K_left, D_left, K_right, D_right, self._dim, R, T,
            cv2.CALIB_ZERO_DISPARITY)

        return dict((("K_left", K_left), ("D_left", D_left),
                     ("K_right", K_right), ("D_right", D_right),
                     ("R", R), ("T", T), ("R_left", R_left),
                     ("R_right", R_right), ("P_left", P_left),
                     ("P_right", P_right), ("Q", Q)))

    def start_calibration(
            self, chessboard=(11, 8), duration=30, number_of_samples=100,
            stereo=True,
            calibration_file=(dirname(abspath(__file__)) +
                              "/../../../../../json/" +
                              "nico_vision_calibration_params.json"),
            overwrite=False,
            term_criteria=(cv2.TERM_CRITERIA_EPS +
                           cv2.TERM_CRITERIA_MAX_ITER, 30, 0.1),
            calibration_flags=(cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC +
                               cv2.fisheye.CALIB_CHECK_COND +
                               cv2.fisheye.CALIB_FIX_SKEW)):
        """
        https://medium.com/@kennethjiang/calibrate-fisheye-lens-using-opencv-333b05afa0b0
        """

        self._chessboard = chessboard
        self._criteria = term_criteria
        self._calibration_flags = calibration_flags
        # 2d points in image plane.
        self._imgpoints = [[]] * len(self._deviceIds)
        self._rvals = [False] * len(self._deviceIds)
        self._chess_detection_barrier = Barrier.Barrier(len(self._deviceIds))
        devicenames = MultiCamRecorder.get_devices()
        devicenames = map(lambda i: devicenames[i], self._deviceIds)
        # load preexisting calibrations from file
        if isfile(calibration_file):
            with open(calibration_file, 'r') as existing_file:
                existing_calibration = json.load(existing_file)
                if (stereo and str(devicenames) not in existing_calibration[
                        "stereo"]):
                    existing_calibration["stereo"][str(devicenames)] = {}
                elif not stereo:
                    for name in devicenames:
                        if name not in existing_calibration["mono"]:
                            existing_calibration["mono"][name] = {}
        else:
            existing_calibration = {"stereo": {str(devicenames): {}},
                                    "mono": dict(zip(devicenames,
                                                     [{}] * len(devicenames)))}
        # abort if calibration for device and dim already exists and overwrite
        # not enabled
        if not overwrite:
            if (stereo and str(self._dim) in existing_calibration["stereo"]
                    [str(devicenames)]):
                logging.warning(("Calibration aborted - Overwrite not " +
                                 "enabled and setting for devices {} and " +
                                 "dimension {} already exists in {}"
                                 ).format(devicenames, self._dim,
                                          calibration_file))
                return
            elif not stereo:
                for i in range(len(self._deviceIds)):
                    if (str(self._dim) in existing_calibration["mono"]
                            [str(devicenames[i])]):
                        logging.warning(("Calibration aborted - Overwrite " +
                                         "not enabled and setting for " +
                                         "device {} and dimension {} " +
                                         "already exists in {}"
                                         ).format(devicenames[i], self._dim,
                                                  calibration_file))
                        return
        # start recording
        logging.info("Start recording images for calibration")
        self._recorder.add_callback(self._callback)
        self._recorder._open = True
        time.sleep(duration)
        self._chess_detection_barrier.abort()
        self._recorder.stop_recording()
        self._stop_event.set()
        self._display.join()
        time.sleep(1)
        cv2.destroyAllWindows()
        logging.info("Recording finished - preparing for calibration")
        # reduce recorded image points to number of samples
        new_length = min(number_of_samples, len(
            self._imgpoints[0]), len(self._imgpoints[1]))
        self._imgpoints = map(lambda x: takespread(
            x, new_length), self._imgpoints)
        # start calibration
        if stereo:
            calib_params = self._calibrate_stereo()
            if calib_params:
                existing_calibration["stereo"][str(devicenames)][str(
                    self._dim)] = calib_params
        else:
            for i in range(len(self._deviceIds)):
                calib_params = self._calibrate_mono(i)
                if calib_params:
                    existing_calibration["mono"][devicenames[i]][str(
                        self._dim)] = calib_params
        # save results
        logging.info("Calibration finished - saving results")
        logging.debug("Saving calibration {}".format(existing_calibration))
        with open(calibration_file, 'w') as outfile:
            json.dump(existing_calibration, outfile, cls=NumpyEncoder)


if __name__ == '__main__':
    logging.getLogger().setLevel(logging.INFO)
    calibrator = CameraCalibrator(width=640, height=480, framerate=10)
    # to reduce complexity of calibration, 100 (number_of_samples) evenly
    # distributed samples will be taken from the total amount of recorded
    # frames
    calibrator.start_calibration(
        stereo=False, duration=60, number_of_samples=100)
