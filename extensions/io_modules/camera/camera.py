"""
V4L Camera
"""
import queue
import threading
import time
import traceback
import subprocess
import cv2 as cv
from typing import Optional, Dict, Union, List
import base64
from datetime import datetime

import environ

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule

from io_modules.camera.config import CameraConfig
from vif.file_helpers.creation import create_directory

from vif.data_interface.network_messages import Status


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='Camera')
    CAMERA_PATH = environ.var(help='Camera device path', default='/dev/video0')


class Camera(IOModule):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME

        self._camera_path = self._environ_config.CAMERA_PATH

        self._thread_handling_lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._thread_stop_event = threading.Event()

        self._video_writer: Optional[cv.VideoWriter] = None
        self._timecodes_file = None
        self._writer_lock = threading.Lock()
        self._frame_count = 0
        self._time_ns_first_frame = 0
        self._time_ns_last_frame = 0
        self._video_filename = ""
        self._timecodes_filename = ""
        self._transformed_filename = ""

        # start export thread right away
        self._export_queue = queue.Queue()
        self._export_stop_event = threading.Event()
        self._export_thread = threading.Thread(target=self._export_thread_fn, name='video_exporter')
        self._export_thread.start()

        # values parsed from config
        self._resolution_camera = (320, 240)  # resolution of hardware input
        self._resolution = (320, 240)  # rotated resolution
        self._fps = 15
        self._rotation = None

        # preview image
        self._preview_resolution = (320, 180)  # (640, 360)
        self._preview_image = None

        # mcap image
        self._mcap_resolution = (320, 180)

    def stop(self):
        self._stop_thread()
        iter_count = 0
        while not self._export_queue.empty() and iter_count < 10:
            time.sleep(0.1)
            iter_count += 1
        self._export_stop_event.set()
        self._export_thread.join()
        self.logger.info('module closed')

    def _export_thread_fn(self):
        while not self._export_stop_event.is_set():
            try:
                export_job = self._export_queue.get(timeout=0.25)
            except queue.Empty:
                continue

            # get file names
            video_filename = export_job[0]
            timecodes_filename = export_job[1]
            transformed_filename = export_job[2]

            # log export
            self.logger.debug("Transform video file: " + video_filename)

            # create mp4fpsmod command
            mp4fpsmod_call = f'mp4fpsmod -o {transformed_filename} -t {timecodes_filename} {video_filename}'

            # log command
            self.logger.debug(mp4fpsmod_call)

            # execute command
            mp4fpsmod_return_code = subprocess.call(mp4fpsmod_call, shell=True)

            # check if no errors occurred
            if mp4fpsmod_return_code != 0:
                msg = f"{video_filename} - mp4fpsmod returned {mp4fpsmod_return_code}"
                self.logger.error(msg)
                self.module_interface.log_gui(msg)
            else:
                self.logger.info(f"{video_filename} - export done")
                self.module_interface.log_gui(f"{video_filename} - export done")
                # TODO check filesize
                # TODO delete files if all OK

            # TODO GUI feedback

    def _worker_thread_fn(self):
        self.logger.debug('worker thread running')

        # get resolution and fps from config
        config = self.config_handler.config
        mcap_enabled = config['enable_mcap']
        mp4_enabled = config['enable_mp4']
        preview_enabled = config['enable_preview']
        mp4_interval = config['mp4_interval']
        mcap_interval = config['mcap_interval']
        live_source = config['live_source']
        center_dot = config['dot_in_center_size']
        crosshair = config['crosshair_size']
        preview_interval = 1

        # init video capture (first available camera)
        cap = cv.VideoCapture(self._camera_path)
        cap.set(cv.CAP_PROP_FRAME_WIDTH, self._resolution_camera[0])
        cap.set(cv.CAP_PROP_FRAME_HEIGHT, self._resolution_camera[1])
        cap.set(cv.CAP_PROP_FOURCC, cv.VideoWriter_fourcc(*config['codec']))
        cap.set(cv.CAP_PROP_FPS, self._fps)

        # get initial timestamps
        mp4_timestamp = time.time()
        mcap_timestamp = mp4_timestamp
        preview_timestamp = mp4_timestamp

        # frame counts
        mcap_frame_count = 0
        preview_frame_count = 0

        error_shown = False

        try:
            while not self._thread_stop_event.is_set():
                # get next frame
                ret, frame = cap.read()

                # get time stamp in ns, s, only sec and only fractional seconds
                time_ns = time.time_ns()
                time_s = time_ns / 1e9
                time_sec = int(time_s)
                time_frac_ns = int(time_ns - time_sec * 1e9)

                # make sure there is a frame
                if not ret:
                    if not error_shown:
                        self.logger.error("Frame Capture Error.")
                        self.module_interface.log_gui("Frame Capture Error.")
                        error_shown = True
                    self._thread_stop_event.wait(0.001)
                    continue
                error_shown = False

                # rotate frame if configured
                if self._rotation is not None:
                    frame = cv.rotate(frame, self._rotation)

                if center_dot > 0:
                    frame = cv.circle(frame, (int(self._resolution[0]/2), int(self._resolution[1]/2)),
                                      radius=0, color=(0, 0, 255), thickness=center_dot)

                if crosshair > 0:
                    frame[:, int(self._resolution[0] / 2 - crosshair/2):
                             int(self._resolution[0] / 2 + crosshair/2)] = [0, 0, 255]
                    frame[int(self._resolution[1] / 2 - crosshair/2):
                          int(self._resolution[1] / 2 + crosshair/2), :] = [0, 0, 255]

                if config["print_timestamp"]:
                    printed_ts = datetime.fromtimestamp(time_s).strftime("%Y-%m-%d %H:%M:%S.%f")
                    try:
                        printed_time, printed_ms = printed_ts.split(".")
                        if len(printed_ms) > 3:
                            printed_ms = printed_ms[:3]
                        printed_ts = printed_time + "." + printed_ms
                    except Exception as e:
                        self.logger.warning(f"Could not process printed timestamp: {e}.")
                    cv.putText(frame, printed_ts, (20, 40), cv.FONT_HERSHEY_SIMPLEX,
                               0.75, (40, 40, 220), 2, cv.LINE_AA)

                # store frame in mp4 video file
                if mp4_enabled and time_s > mp4_timestamp:
                    #self.logger.debug("Sample mp4")
                    self._frame_count += 1

                    # write frame to mp4 file
                    with self._writer_lock:
                        if self._video_writer is not None and self.module_interface.capturing_active():
                            # write video frame
                            self._video_writer.write(frame)

                            # write timestamp to timecode file
                            if self._time_ns_first_frame == 0:
                                self._timecodes_file.write('0\n')
                                self._time_ns_first_frame = time_ns
                            else:
                                time_diff = str(round((time_ns - self._time_ns_first_frame) / 1e6, 3))
                                self._timecodes_file.write(time_diff + '\n')

                            self._time_ns_last_frame = time_ns

                    # store frame as live data if selected
                    if live_source == "mp4":
                        jpg_image = cv.imencode(".jpg", frame)[1]

                        # create data frame
                        data = {'timestamp': {'sec:': time_sec, 'nsec': time_frac_ns},
                                'frame_id': str(self._frame_count),
                                'data': base64.b64encode(jpg_image).decode(),
                                'format': 'jpeg',
                                'res_x': self._resolution[0],
                                'res_y': self._resolution[1]}

                        # store image in data dict
                        self.data_broker.data_in(time_ns, data, mcap=False, live=True, latest=False)

                    # advance to next mp4 sample time
                    mp4_timestamp += mp4_interval

                # store frame in mcap file
                if mcap_enabled and time_s > mcap_timestamp:
                    #self.logger.debug("Sample MCAP")
                    mcap_frame_count += 1

                    # resize image frame and store as preview image
                    resized_frame = cv.resize(frame, self._mcap_resolution)
                    mcap_image = cv.imencode(".jpg", resized_frame)[1]

                    # create data frame
                    data = {'timestamp': {'sec:': time_sec, 'nsec': time_frac_ns},
                            'frame_id': str(mcap_frame_count),
                            'data': base64.b64encode(mcap_image).decode(),
                            'format': 'jpeg',
                            'res_x': self._mcap_resolution[0],
                            'res_y': self._mcap_resolution[1]}

                    # store image in data dict
                    self.data_broker.data_in(time_ns, data, live=live_source == "mcap", latest=False)

                    # advance to next mcap sample time
                    mcap_timestamp += mcap_interval

                # update preview image if enabled
                if preview_enabled and time_s > preview_timestamp:
                    #self.logger.debug("Sample Preview")
                    preview_frame_count += 1
                    resized_frame = cv.resize(frame, self._preview_resolution)
                    self._preview_image = cv.imencode(".jpg", resized_frame)[1]

                    # create data frame
                    data = {'timestamp': {'sec:': time_sec, 'nsec': time_frac_ns},
                            'frame_id': str(preview_frame_count),
                            'data': base64.b64encode(self._preview_image).decode(),
                            'format': 'jpeg',
                            'res_x': self._preview_resolution[0],
                            'res_y': self._preview_resolution[1]}

                    # only latest data in
                    self.data_broker.data_in(time_ns, data, mcap=False, live=live_source == "preview")

                    # advance to next preview sample time
                    preview_timestamp += preview_interval


        except Exception as e:
            self.logger.error(f'Exception in worker: {type(e).__name__}: {e}\n{traceback.format_exc()}')

        cap.release()
        self.logger.debug('thread gone')

    def _start_thread(self, locking=True):
        if locking:
            self._thread_handling_lock.acquire()

        if self._worker_thread and self._worker_thread.is_alive():
            self.logger.warning('_start_thread: thread already running')
        else:
            self._worker_thread = threading.Thread(target=self._worker_thread_fn, name='worker')
            self._thread_stop_event.clear()
            self._worker_thread.start()

        if locking:
            self._thread_handling_lock.release()

    def _stop_thread(self, locking=True):
        if locking:
            self._thread_handling_lock.acquire()

        if self._worker_thread:
            self._thread_stop_event.set()
            self._worker_thread.join()
            self._worker_thread = None

        if locking:
            self._thread_handling_lock.release()

    def command_prepare_sampling(self):
        self.logger.info('prepare sampling!')
        self._start_thread()

    def command_stop_sampling(self):
        self.logger.info('stop sampling!')
        self._stop_thread()

    def command_prepare_capturing(self) -> None:
        # get file names
        path_dir = self.module_interface.data_broker.get_module_data_dir(self.module_interface.state.measurement_info.name)
        create_directory(path_dir)
        self._video_filename = str(path_dir) + "/video_raw.mp4"
        self._timecodes_filename = str(path_dir) + "/timecodes.txt"
        self._transformed_filename = str(path_dir) + "/video.mp4"

        # create video writer
        with self._writer_lock:
            self.logger.debug("Create Video File: %s with FPS: %d and Resolution: %d x %d",
                              self._video_filename, self._fps, self._resolution[0], self._resolution[1])
            self._frame_count = 0
            self._time_ns_first_frame = 0
            self._time_ns_last_frame = 0
            self._video_writer = cv.VideoWriter(self._video_filename, cv.VideoWriter_fourcc(*'mp4v'),
                                                self._fps, self._resolution)

            # create timecodes file
            self._timecodes_file = open(self._timecodes_filename, 'w')

    def command_stop_capturing(self) -> None:
        with self._writer_lock:
            if self._video_writer is not None:
                self.logger.debug("Finish Video File.")
                self._video_writer.release()
                self._video_writer = None
                self._timecodes_file.close()
                self._timecodes_file = None

                # put export job into queue
                export_job = (self._video_filename, self._timecodes_filename, self._transformed_filename)
                self._export_queue.put(export_job)

    def command_validate_config(self, config) -> Status:
        if not config['preview_resolution'].endswith('p'):
            return Status(error=True, message='Preview resolution must end with "p"')

        if config['mp4_interval'] < 0 or config['mcap_interval'] < 0:
            return Status(error=True, message='MP4 and MCAP intervals must be greater than 0.')

        if config['rotation'] not in ['None', '90 deg CW', '90 deg CCW', '180 deg']:
            return Status(error=True, message='Rotation must be "None", "90 deg CW", "90 deg CCW", or "180 deg"')

        return Status(error=False)

    @staticmethod
    def _resolution_str_to_tuple(resolution_str: str):
        resolution_parts = resolution_str.replace(" ", "").split("x")
        return int(resolution_parts[0]), int(resolution_parts[1])

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        try:
            # make sure thread re-spawn is not intercepted
            with self._thread_handling_lock:
                self._stop_thread(locking=False)

                # parse config values
                self._resolution_camera = self._resolution_str_to_tuple(config['resolution'])
                self._resolution = self._resolution_camera

                if config['rotation'] == '90 deg CW':
                    self.logger.info("rotating video 90 deg CW")
                    self._rotation = cv.ROTATE_90_CLOCKWISE
                    self._resolution = (self._resolution_camera[1], self._resolution_camera[0])
                elif config['rotation'] == '90 deg CCW':
                    self.logger.info("rotating video 90 deg CCW")
                    self._rotation = cv.ROTATE_90_COUNTERCLOCKWISE
                    self._resolution = (self._resolution_camera[1], self._resolution_camera[0])
                elif config['rotation'] == '180 deg':
                    self.logger.info("rotating video 180 deg")
                    self._rotation = cv.ROTATE_180
                else:
                    self._rotation = None

                # calculate preview resolution: use XXXp instead of XXX x XXX
                res_prev_y = int(config['preview_resolution'].strip('p'))
                res_prev_x = int(res_prev_y * self._resolution[0] / self._resolution[1])
                self._preview_resolution = self._resolution_str_to_tuple(f"{res_prev_x}x{res_prev_y}")

                # calculate preview resolution: use XXXp instead of XXX x XXX
                res_mcap_y = int(config['mcap_resolution'].strip('p'))
                res_mcap_x = int(res_mcap_y * self._resolution[0] / self._resolution[1])
                self._mcap_resolution = self._resolution_str_to_tuple(f"{res_mcap_x}x{res_mcap_y}")

                self.logger.info('Resolutions calculated: %dx%d (Preview), %dx%d (MCAP)',
                                 self._preview_resolution[0], self._preview_resolution[1],
                                 self._mcap_resolution[0], self._mcap_resolution[1])
                self._fps = int(config['fps'])

                if self.module_interface.sampling_active() or self.module_interface.capturing_active():
                    self._start_thread(locking=False)

            return Status(error=False)

        except Exception as e:
            self.logger.error(f'error applying config: {type(e).__name__}: {e}\n{traceback.format_exc()}')
            return Status(error=True, title=type(e).__name__, message=str(e))

    def command_get_meta_data(self) -> Dict[str, Union[str, int, float, bool]]:
        duration_s = (self._time_ns_last_frame - self._time_ns_first_frame) / 1e9
        try:
            avg_fps = self._frame_count / duration_s
        except ZeroDivisionError:
            avg_fps = 0
        return {
            'frame_count': self._frame_count,
            'duration_s': duration_s,
            'average_fps': avg_fps
        }

    def command_get_schemas(self) -> List[Dict]:
        return [{
            'topic': f'{self.module_interface.data_broker.replace_name_chars(self.config_handler.type)}',
            'dtype_name': 'foxglove.CompressedImage',
            'type': 'object',
            "properties": {
                "timestamp": {
                  "type": "object",
                  "properties": {
                    "sec": {
                      "type": "integer",
                      "minimum": 0
                    },
                    "nsec": {
                      "type": "integer",
                      "minimum": 0,
                      "maximum": 999999999
                    }
                  }
                },
                "frame_id": {
                  "type": "string",
                },
                "data": {
                  "type": "string",
                  "contentEncoding": "base64",
                },
                "format": {
                  "type": "string",
                }
            }
        }]


if __name__ == '__main__':
    main(Camera, CameraConfig, environ.to_config(ModuleEnv).MODULE_NAME)
