"""
A background thread which collects jobs in a list and publishes them.
Used mainly for GUI tasks
"""

import threading
import json
from typing import List, Dict, Optional

from vif.logger.logger import LoggerMixin
from vif.jobs.job_entry import JobEntry, TimeJob
from vif.data_interface.connection_manager import ConnectionManager, Key


class JobServer(LoggerMixin):
    def __init__(self, *args, cm: ConnectionManager, db_id: str, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug("Creating Job Server.")
        self._cm: ConnectionManager = cm
        self._db_id: str = db_id
        self._job_id_counter: int = 0
        self._jobs: List[JobEntry] = []
        self._jobs_lock: threading.Lock = threading.Lock()
        self._update_event: threading.Event = threading.Event()
        self._time_job: TimeJob = TimeJob(cm, db_id)
        self._queryables: List[str] = []
        self._publishers: List[int] = []
        self.pub_job_list_topic: Key = Key(self._db_id, 'c', 'job_list')
        self._kill: bool = False
        self._run_thread: Optional[threading.Thread] = threading.Thread(target=self._run, name='job_server_run')

    def start(self):
        """
        Starts the background thread and declares the necessary connection endpoints.
        """
        for key, cb in [(Key(self._db_id, 'c', 'job_submit'), self._cb_job_submit),
                        (Key(self._db_id, 'c', 'job_update'), self._cb_job_update)
                        ]:
            self._queryables.append(self._cm.declare_queryable(key, cb))

        self._publishers.append(self._cm.declare_publisher(self.pub_job_list_topic))

        self._kill = False
        assert self._run_thread is not None, 'JobServer cannot be re-started'
        self._run_thread.start()

        self.add(self._time_job)

    def stop(self):
        """
        Stops the JobServer.
        """
        self.logger.debug("Stopping Job Server.")
        self._kill = True
        self._update_event.set()
        if self._run_thread is not None:
            self._run_thread.join()
            self._run_thread = None

        for q in self._queryables:
            self._cm.undeclare_queryable(q)
        self._queryables.clear()

        for p in self._publishers:
            self._cm.undeclare_publisher(p)
        self._publishers.clear()
        self.logger.debug('done')

    def add(self, job: JobEntry):
        """
        Appends a new job to the job list.
        """
        # create new job entry from given json
        self._job_id_counter += 1
        job.set_id(self._job_id_counter)
        self._update_event.set()

        # add new job to jobs-list
        with self._jobs_lock:
            self._jobs.append(job)

    def update(self):
        """
        Allows the background thread to progress and publish the next job message.
        """
        self._update_event.set()

    def _cb_job_submit(self, data: bytes) -> str | bytes:
        """
        A callback to allow other modules to append a new job to the job list.
        """
        # increment job id counter
        self._job_id_counter += 1

        # create new job entry from given json
        job = JobEntry(self._cm, self._db_id)
        job.from_json(json.loads(data))
        job.set_id(self._job_id_counter)

        # add new job to jobs-list
        with self._jobs_lock:
            self._jobs.append(job)

        # send back the job id
        return json.dumps({'id': self._job_id_counter})

    def _cb_job_update(self, data: bytes) -> str | bytes:
        """
        A callback to allow other modules to update job in the job list.
        """
        # deserialize json
        job_json = json.loads(data)

        # get job id
        job_id = job_json['id']

        # update job in jobs list
        with self._jobs_lock:
            for job in self._jobs:
                if job.get_id() == job_id:
                    job.from_json(job_json)
                    break

        return json.dumps({'id': job_id})

    def _run(self) -> None:
        """
        The background thread method, which handles the controlled publishing of the jobs.
        """
        self.logger.debug('thread started')
        while not self._kill:
            # update slow if there are no jobs, otherwise increase update rate
            sleep_time = 1.0 if len(self._jobs) > 0 else 1.0

            # wait for event or sleep time
            self._update_event.wait(timeout=sleep_time)
            self._update_event.clear()

            # kill if flag is set
            if self._kill:
                break

            self._time_job.update_time()

            # create json dict with top level entry
            job_json: Dict[str, List[Dict]] = {'jobs': []}

            with self._jobs_lock:
                # append job dicts to json
                for job in self._jobs:
                    job_json['jobs'].append(job.get_dict())

                # get rid of jobs that are marked as done, for next iteration
                self._jobs = [job for job in self._jobs if not job.is_done()]

            # publish current jobs
            # self.logger.debug("JOBS: " + json.dumps(job_json))
            self._cm.publish(self.pub_job_list_topic, json.dumps(job_json))
