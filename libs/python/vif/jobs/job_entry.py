import json
import traceback
from datetime import datetime, timezone

from vif.logger.logger import LoggerMixin
from vif.data_interface.connection_manager import ConnectionManager, Key


class JobEntry(LoggerMixin):
    def __init__(self, cm: ConnectionManager, db_id: str):
        super().__init__()
        self._cm = cm
        self._db_id = db_id
        self._id = -1
        self._type: str = "export"
        self._done: bool = False
        self._data = {}

    def update(self):
        # submit job if id is not set
        if self._id == -1:
            try:
                message = json.dumps(self.get_dict())
                reply = self._cm.request(Key(self._db_id, 'c', 'job_submit'), message)
                self._id = json.loads(reply)['id']
            except Exception as e:
                self.logger.error(f"Error during job update/submit: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        else:
            # job is already active, update job
            try:
                message = json.dumps(self.get_dict())
                _ = self._cm.request(Key(self._db_id, 'c', 'job_update'), message)
            except Exception as e:
                self.logger.error(f"Error during job update: {type(e).__name__}: {e}\n{traceback.format_exc()}")

        # if we have sent the job with the done flag we can reset this job as the job server will clear the job
        if self._done:
            self._id = -1

    def set_type(self, job_type: str):
        self._type = job_type
        return self

    def set_id(self, job_id: int):
        self._id = job_id
        return self

    def get_id(self):
        return self._id

    def set_done(self):
        self._done = True
        return self

    def is_done(self) -> bool:
        return self._done

    def set_data(self, key, value):
        self._data[key] = value

    def get_data(self, key):
        return self._data[key]

    def from_json(self, json_job):
        self._id = json_job['id']
        self._type = json_job['type']
        self._done = json_job['done']
        self._data = json_job['data']

    def get_dict(self):
        job_dict = {'id': self._id,
                    'type': self._type,
                    'done': self._done,
                    'data': self._data}

        return job_dict


class TimeJob(JobEntry):
    def __init__(self, cm: ConnectionManager, db_id: str):
        super().__init__(cm, db_id)
        self.set_type("time")

        # init data
        self.set_data("name", "Time")
        self.set_data("description", "Time")

    def update_time(self):
        time_ns = datetime.now(timezone.utc)
        time_str = time_ns.strftime("%H:%M:%S")
        self.set_data("time_ns", int(time_ns.timestamp() * 1_000_000) * 1000)
        self.set_data("time_str", time_str)


class BusyJob(JobEntry):
    def __init__(self, cm: ConnectionManager, db_id: str):
        super().__init__(cm, db_id)

        self.set_type("busy")
        self.set_name("None")
        self.set_description("")

    def set_name(self, name: str):
        self.set_data("name", name)
        return self

    def set_description(self, description: str):
        self.set_data("description", description)
        return self


class LogJob(JobEntry):
    def __init__(self, cm: ConnectionManager, db_id: str):
        super().__init__(cm, db_id)

        self.set_type("log")
        self.set_name("None")
        self.set_message("none")
        self.set_time("00:00:00")

    def set_name(self, name: str):
        self.set_data("name", name)
        return self

    def set_message(self, message: str):
        self.set_data("message", message)
        return self

    def set_time(self, time_string: str):
        self.set_data("time_str", time_string)
        return self


class StateJob(JobEntry):
    def __init__(self, cm: ConnectionManager, db_id: str):
        super().__init__(cm, db_id)
        self.set_type("state")
        self.set_capture(False)
        self.set_sampling(False)

    def set_capture(self, state: bool):
        self.set_data("capture", state)
        return self

    def set_sampling(self, state: bool):
        self.set_data("sampling", state)
        return self


class ReadyJob(JobEntry):
    def __init__(self, cm: ConnectionManager, db_id: str):
        super().__init__(cm, db_id)
        self.set_type("ready")
        self.set_ready(True)
        self.set_module_name("none")

    def set_module_name(self, module_name: str):
        self.set_data("module_name", module_name)
        return self

    def set_ready(self, state: bool):
        self.set_data("ready", state)
        return self

    def get_ready(self):
        return self.get_data("ready")


class EventJob(JobEntry):
    def __init__(self, cm: ConnectionManager, db_id: str):
        super().__init__(cm, db_id)
        self.set_type("event")
        self.set_modules_changed(False)
        self.set_files_changed(False)
        self.set_meta_changed(False)

    def set_modules_changed(self, state: bool):
        self.set_data("modules_changed", state)
        return self

    def set_files_changed(self, state: bool):
        self.set_data("files_changed", state)
        return self

    def set_meta_changed(self, state: bool):
        self.set_data("meta_changed", state)
        return self
