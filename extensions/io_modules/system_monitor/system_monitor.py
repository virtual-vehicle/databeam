"""
System Monitor Module
"""
import threading
import traceback
from typing import Optional, Dict, List
import time

import environ
import psutil
import docker

from vif.data_interface.module_interface import main
from vif.data_interface.io_module import IOModule
from vif.asyncio_helpers.asyncio_helpers import tick_generator

from io_modules.system_monitor.config import SystemMonitorConfig

from vif.data_interface.network_messages import Status

# get rid of urrlib3 debug logs
import logging
logging.getLogger("urllib3").setLevel(logging.WARNING)


@environ.config(prefix='')
class ModuleEnv:
    MODULE_NAME = environ.var(help='Name of this instance', default='SystemMonitor')


class SystemMonitor(IOModule):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.logger.debug('initializing')
        self._environ_config = environ.to_config(ModuleEnv)
        self.name = self._environ_config.MODULE_NAME

        self.docker_client = docker.from_env()

        self._thread_handling_lock = threading.Lock()
        self._worker_thread: Optional[threading.Thread] = None
        self._thread_stop_event = threading.Event()

        self._cpu_load_thread: Optional[threading.Thread] = None
        self._cpu_load = None
        self._cpu_load_lock = threading.Lock()
        self._cpu_load_ready_event = threading.Event()

    def _cpu_load_worker(self):
        self.logger.debug('CPU load worker thread running')
        update_interval = self.config_handler.config['update_interval_seconds']

        try:
            num_cores = psutil.cpu_count()
            while not self._thread_stop_event.is_set():
                cpu_load = {}
                average = 0
                for i, core_load in enumerate(psutil.cpu_percent(interval=0.5, percpu=True)):
                    cpu_load[f"core_{i}"] = core_load
                    average += core_load
                average /= num_cores
                cpu_load["core_average"] = average

                with self._cpu_load_lock:
                    self._cpu_load = cpu_load
                self._cpu_load_ready_event.set()

                self._thread_stop_event.wait(update_interval)
        except Exception as e:
            self.logger.error(f'Exception in CPU load worker thread: {e}')

        self.logger.debug("CPU load worker thread gone.")

    def _get_cpu_load(self):
        with self._cpu_load_lock:
            return self._cpu_load

    def _get_num_cpu_loads(self):
        return psutil.cpu_count()

    def _get_core_temperatures(self):
        result = {}
        temperatures = psutil.sensors_temperatures()
        if 'coretemp' in temperatures:
            result['coretemp'] = {}
            for i, item in enumerate(temperatures['coretemp']):
                result['coretemp'][f"temp_{i}"] = item.current
        return result

    def _get_num_core_temperatures(self):
        return len(self._get_core_temperatures()['coretemp'].keys())

    def _get_memory_load(self):
        memory_load = psutil.virtual_memory()
        gigabyte_available = memory_load.total / (1024**3)
        gigabyte_free = memory_load.available / (1024**3)
        percent_used = memory_load.percent
        return {"mem_available": gigabyte_available, "mem_free": gigabyte_free, "mem_percent_used": percent_used}

    def _get_disk_usage(self, paths):
        result = {}
        for i, path in enumerate(paths):
            path_id = f"{i}"
            try:
                disk_usage = psutil.disk_usage(path)
                gigabyte_total = disk_usage.total / (1024**3)
                gigabyte_used = disk_usage.used / (1024**3)
                gigabyte_free = disk_usage.free / (1024**3)
                percent_used = disk_usage.percent
                result[path_id] = {
                    f'disk_{i}_path': path,
                    f'disk_{i}_total': gigabyte_total,
                    f'disk_{i}_used': gigabyte_used,
                    f'disk_{i}_free': gigabyte_free,
                    f'disk_{i}_percent': percent_used
                }
            except Exception as e:
                self.logger.warning(f"Ran into exception while reading disk usage: {e}")
                result[path_id] = {
                    f'disk_{i}_path': path,
                    f'disk_{i}_total': 0,
                    f'disk_{i}_used': 0,
                    f'disk_{i}_free': 0,
                    f'disk_{i}_percent': 0
                }
        return result

    def _get_docker_status(self):
        containers_list = self.docker_client.containers.list(all=True)

        json = {"containers": []}

        for container in containers_list:
            if container.status != 'running':
                continue
            container_tags = ""
            try:
                container_tags = container.image.tags[0]
            except IndexError:
                pass
            container_dict = {
                "name": container.name,
                "image": container_tags,
                "status": container.status
            }
            json["containers"].append(container_dict)
        return json

    def stop(self):
        self._stop_thread()
        self.logger.info('module closed')

    def _worker_thread_fn(self):
        self.logger.debug('worker thread running')
        update_interval = self.config_handler.config['update_interval_seconds']

        g = tick_generator(update_interval, drop_missed=True, time_source=time.time)
        try:
            while not self._thread_stop_event.is_set():

                cpu_load = self._get_cpu_load()

                # wait until cpu load is ready
                if cpu_load is None:
                    continue

                core_temperatures = self._get_core_temperatures()
                memory_load = self._get_memory_load()
                disk_status = self._get_disk_usage(self.config_handler.config['disk_directories'])
                data = {**cpu_load, **core_temperatures['coretemp'], **memory_load}

                for v in disk_status.values():
                    data.update(v)

                # self.logger.debug('%s', data)
                self.data_broker.data_in(time.time_ns(), data)

                # wait for timeout or killed thread
                self._thread_stop_event.wait(timeout=next(g))
        except Exception as e:
            self.logger.error(f'Exception in worker: {type(e).__name__}: {e}\n{traceback.format_exc()}')
        g.close()
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

        if self._cpu_load_thread is None:
            self._cpu_load_thread = threading.Thread(target=self._cpu_load_worker, name='cpu_load_worker', daemon=True)
            self._cpu_load_thread.start()

        if locking:
            self._thread_handling_lock.release()

    def _stop_thread(self, locking=True):
        if locking:
            self._thread_handling_lock.acquire()

        if self._worker_thread:
            self._thread_stop_event.set()
            self._worker_thread.join()
            self._cpu_load_thread.join()
            self._worker_thread = None
            self._cpu_load_thread = None

        if locking:
            self._thread_handling_lock.release()

    def command_validate_config(self, config) -> Status:
        update_interval = config['update_interval_seconds']

        if update_interval < 1:
            return Status(error=True, title="Update Interval", message='Update interval must be >= 1')

        return Status(error=False)

    def command_apply_config(self) -> Status:
        # get a local copy of the current config
        config = self.config_handler.config
        self.logger.info('apply config: %s', config)

        try:
            # make sure thread re-spawn is not intercepted
            with self._thread_handling_lock:
                self._stop_thread(locking=False)

                if self.module_interface.sampling_or_capturing_active():
                    self._start_thread(locking=False)

            return Status(error=False)

        except Exception as e:
            self.logger.error(f'error applying config: {type(e).__name__}: {e}\n{traceback.format_exc()}')
            return Status(error=True, title=type(e).__name__, message=str(e))

    def command_prepare_sampling(self):
        self.logger.info('prepare sampling!')
        self._start_thread()

    def command_stop_sampling(self):
        self.logger.info('stop sampling!')
        self._stop_thread()

    def command_get_schemas(self) -> List[Dict]:
        num_type = {'type': 'number'}
        str_type = {'type': 'string'}
        cpu_load_props = {"core_" + str(x): num_type for x in range(self._get_num_cpu_loads())}
        cpu_load_props['core_average'] = num_type
        core_temp_props = {"temperature_" + str(x): num_type for x in range(self._get_num_core_temperatures())}
        memory_props = {x: num_type for x in ['mem_available', 'mem_free', 'mem_percent_used']}

        docker_props = {'docker_status': {'type': 'string'}}
        num_disks = len(self.config_handler.config['disk_directories'])
        disk_props = {}
        for i in range(num_disks):
            disk_props.update({f'disk_{i}_' + k: v for k, v in zip(['path', 'total', 'used', 'free', 'percent'],
                                                                   [str_type] + [num_type] * 4)})
        props = {**cpu_load_props, **core_temp_props, **memory_props, **disk_props, **docker_props}

        return [{
            'type': 'object',
            'properties': props
        }]


if __name__ == '__main__':
    main(SystemMonitor, SystemMonitorConfig, environ.to_config(ModuleEnv).MODULE_NAME)
