"""
The server script for the rest api. Sets up the http routes.
Also hosts the WebGUI.
Routes can be used externally to communicate with DataBeam.
"""

import threading
from typing import Optional, Dict, List
import os
import queue
from pathlib import Path
import json
import random
import string
import hashlib

import docker
import flask
import flask_login
import zipfly

from flask import Flask, render_template, request, jsonify, make_response, stream_with_context, send_from_directory
from flask_cors import CORS
from werkzeug.serving import make_server, BaseWSGIServer

from vif.logger.logger import LoggerMixin

from controller_api import ControllerAPI
from file_api import FileAPI
from preview_api import PreviewAPI

import logging
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

class User(flask_login.UserMixin):
    def __init__(self):
        pass

class Server(LoggerMixin):
    def __init__(self, *args, controller_api: ControllerAPI, file_api: FileAPI, preview_api: PreviewAPI, shutdown_queue,
                 login_user_names_str: str, login_password_hashes_str: str, data_dir, logs_dir, secret_key, **kwargs):
        super().__init__(*args, **kwargs)

        self._controller_api: ControllerAPI = controller_api
        self._file_api: FileAPI = file_api
        self._preview_api: PreviewAPI = preview_api
        self._shutdown_queue: queue.Queue = shutdown_queue
        self._data_dir: Path = data_dir
        self._logs_dir: Path = logs_dir

        self._worker_thread: Optional[threading.Thread] = None
        self._thread_event: threading.Event = threading.Event()

        self._client_id_counter: int = 0
        self._batch_measurement_names: Dict[int, List[str]] = {}
        self._batch_id_counter: int = 0

        self._cfg: Dict[str, int] = {
            'port': 5000
        }

        # set log level for docker api http requests
        logging.getLogger("urllib3").setLevel(logging.ERROR)

        # create docker client
        self._docker_client: docker.DockerClient = docker.from_env()

        # create random hash padding
        self._random_hash_padding: str = ''.join(random.choice(string.ascii_letters) for _ in range(10))

        # create user database from env
        self._user_name_list: List[str] = login_user_names_str.split("#")
        self._password_hashes_list: List[str] = login_password_hashes_str.split("#")
        self._user_dict: Dict[str, str] = {k: v for k, v in zip(self._user_name_list, self._password_hashes_list)}

        self.app: Flask = Flask("REST Server")
        # set a random string
        self.app.secret_key: str = secret_key
        self._login_manager: flask_login.LoginManager = flask_login.LoginManager(self.app)
        self._login_manager.init_app(self.app)
        self._login_manager.user_loader(self.user_loader)
        self._login_manager.unauthorized_handler(self.route_unauthorized)
        #self._login_manager.request_loader(self.request_loader)
        CORS(self.app)
        self.app.add_url_rule('/', 'home', self.route_home, methods=['GET'])
        self.app.add_url_rule('/login', 'login', self.route_login, methods=['GET', 'POST'])
        self.app.add_url_rule('/login_padding', 'login_padding', self.route_login_padding, methods=['GET'])
        self.app.add_url_rule('/favicon.ico', "favicon", self.route_favicon, methods=['GET'])
        self.app.add_url_rule('/start_sampling', 'start_sampling', self.route_start_sampling, methods=['POST'])
        self.app.add_url_rule('/stop_sampling', 'stop_sampling', self.route_stop_sampling, methods=['POST'])
        self.app.add_url_rule('/start', 'start', self.route_start, methods=['POST'])
        self.app.add_url_rule('/stop', 'stop', self.route_stop, methods=['POST'])
        self.app.add_url_rule('/shutdown', 'shutdown', self.route_shutdown, methods=['GET'])
        self.app.add_url_rule('/modules', 'modules', self.route_modules, methods=['GET'])
        self.app.add_url_rule('/preview', 'preview', self.route_preview, methods=['POST'])
        self.app.add_url_rule('/meta', 'get_meta', self.route_get_meta, methods=['GET'])
        self.app.add_url_rule('/user_meta', 'set_user_meta', self.route_set_user_meta, methods=['POST'])
        self.app.add_url_rule('/system_meta', 'set_system_meta', self.route_set_system_meta, methods=['POST'])
        self.app.add_url_rule('/modules/config/<string:module_name>', 'modules_config',
                              self.route_config, methods=['GET'])
        self.app.add_url_rule('/modules/default_config/<string:module_name>', 'modules_default_config',
                              self.route_default_config, methods=['GET'])
        self.app.add_url_rule('/modules/apply_config/<string:module_name>', 'modules_apply_config',
                              self.route_apply_config, methods=['POST'])
        self.app.add_url_rule('/modules/config_button/<string:module_name>', 'modules_config_button',
                              self.route_config_button, methods=['POST'])
        self.app.add_url_rule('/modules/data_config/<string:module_name>', 'modules_data_config',
                              self.route_data_config, methods=['POST'])
        self.app.add_url_rule('/modules/documentation/<string:module_name>', 'modules_documentation',
                              self.route_documentation, methods=['GET'])
        self.app.add_url_rule('/measurements', 'measurements', self.route_measurements, methods=['GET'])
        self.app.add_url_rule('/download/measurement/<string:measurement>', 'download_measurement',
                              self.route_download_measurement, methods=['GET'])
        self.app.add_url_rule('/download/batch_list', 'download_batch_list',
                              self.route_batch_list, methods=['POST'])
        self.app.add_url_rule('/download/batch/<string:batch_id>', 'download_batch',
                              self.route_download_batch, methods=['GET'])
        self.app.add_url_rule('/remove/measurements', 'remove_measurements',
                              self.route_remove_measurements, methods=['POST'])
        self.app.add_url_rule('/docker/containers', 'docker_containers',
                              self.route_docker_containers, methods=['GET'])
        self.app.add_url_rule('/docker/logs/<string:container_id>', 'docker_logs',
                              self.route_docker_logs, methods=['GET'])
        self.app.add_url_rule('/system_cmd', 'system_command', self.route_system_command, methods=['POST'])
        self.app.add_url_rule('/download/logs', 'download_logs',
                              self.route_download_logs, methods=['GET'])
        self._server: BaseWSGIServer = make_server('0.0.0.0', self._cfg['port'], self.app)
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.start()
        self.logger.info("Flask Running")

    @flask_login.login_required
    def route_home(self):
        return render_template('index.html')

    def user_loader(self, id):
        #self.logger.debug("Load User: " + id)
        user = User()
        user.id = id
        return user

    def route_unauthorized(self):
        return flask.redirect(flask.url_for('login'))

    def route_login(self):
        if flask.request.method == 'POST':
            data = request.json

            # get password hash
            user_name = data['user']
            password_hash = data['password']

            # log the received password hash
            self.logger.info(f'User "{user_name}" trying to login with password hash "{password_hash}"')

            # we respond with fail or ok to log in
            response = {'login': 'fail'}

            # check if user is present
            if user_name not in self._user_dict.keys():
                return jsonify(response)

            # compute stored password hash with padding
            hash_padded = hashlib.sha256((self._user_dict[user_name] + self._random_hash_padding).encode('utf-8')).digest().hex()

            # login user if password hashes match
            if password_hash == hash_padded:
                user = User()
                user.id = user_name
                flask_login.login_user(user)
                response['login'] = 'ok'
                self.logger.info(f'User "{user_name}" successfully logged in.')

            # set new random hash padding
            self._random_hash_padding = ''.join(random.choice(string.ascii_letters) for _ in range(10))

            return jsonify(response)
        else:
            return render_template('login.html')

    def route_login_padding(self):
        return jsonify({
            'login_padding': self._random_hash_padding
        })

    def route_favicon(self):
        return send_from_directory(os.path.join(self.app.root_path, 'static/images'),
                                   'favicon.ico', mimetype='image/vnd.microsoft.icon')

    @flask_login.login_required
    def route_start_sampling(self):
        status_dict = self._controller_api.send_command_start_sampling()
        return jsonify(status_dict)

    @flask_login.login_required
    def route_stop_sampling(self):
        status_dict = self._controller_api.send_command_stop_sampling()
        return jsonify(status_dict)

    @flask_login.login_required
    def route_start(self):
        status_dict = self._controller_api.send_command_start_capture()
        return jsonify(status_dict)

    @flask_login.login_required
    def route_stop(self):
        status_dict = self._controller_api.send_command_stop_capture()
        return jsonify(status_dict)

    @flask_login.login_required
    def route_modules(self):
        modules = self._controller_api.get_modules_and_data_config_dict()
        return jsonify(modules)

    @flask_login.login_required
    def route_preview(self):
        data = request.json
        self._preview_api.request_data(data['id'], data['module_name'], schema_index=data['schema_index'])
        return jsonify(data)

    @flask_login.login_required
    def route_get_meta(self):
        meta_data = self._controller_api.get_metadata_dict()
        return jsonify(meta_data)

    @flask_login.login_required
    def route_set_user_meta(self):
        meta_json = request.json
        meta_data = self._controller_api.set_user_meta_string(json.dumps(meta_json['user_meta']))
        return jsonify(meta_data)

    @flask_login.login_required
    def route_set_system_meta(self):
        meta_json = request.json
        meta_data = self._controller_api.set_system_meta_string(json.dumps(meta_json['system_meta']))
        return jsonify(meta_data)

    @flask_login.login_required
    def route_config(self, module_name):
        config = self._controller_api.get_module_config_dict(module_name)
        return jsonify(config)

    @flask_login.login_required
    def route_default_config(self, module_name):
        config = self._controller_api.get_module_default_config_dict(module_name)
        return jsonify(config)

    @flask_login.login_required
    def route_apply_config(self, module_name):
        cfg = request.json
        result = self._controller_api.set_module_config_dict(module_name, cfg)
        return jsonify(result)

    @flask_login.login_required
    def route_config_button(self, module_name):
        event_data = request.json
        result = self._controller_api.set_module_config_event(module_name, event_data)
        return jsonify(result)

    @flask_login.login_required
    def route_data_config(self, module_name):
        data_config = request.json
        result = self._controller_api.set_data_config_dict(module_name, data_config)
        return jsonify(result)

    @flask_login.login_required
    def route_documentation(self, module_name):
        result = self._controller_api.get_documentation(module_name)
        return jsonify(result)

    @flask_login.login_required
    def route_measurements(self):
        modules = self._file_api.get_measurements()
        return jsonify({'measurements': modules})

    @flask_login.login_required
    def route_docker_containers(self):
        json = {"containers": []}

        try:
            containers_list = self._docker_client.containers.list(all=True)
        except Exception as e:
            self.logger.warning(f"Docker container list failed: {type(e)}: {e}")
            return jsonify(json)

        for container in containers_list:
            if container.status != 'running':
                continue

            container_tags = ""
            try:
                container_tags = container.image.tags[0]
            except IndexError:
                pass

            container_dict = {
                "id": container.id,
                "name": container.name,
                "image": container_tags,
                #"labels": container.labels,
                "short_id": container.short_id,
                "status": container.status
            }
            json["containers"].append(container_dict)

        return jsonify(json)

    @flask_login.login_required
    def route_docker_logs(self, container_id: str):
        log_str = "Log for container " + container_id + " not found."

        containers_list = self._docker_client.containers.list(all=True)
        for container in containers_list:
            if container.short_id == container_id:
                log_str = container.logs(timestamps=False).decode("utf-8")

        return jsonify({'logs': log_str})

    @flask_login.login_required
    def route_download_measurement(self, measurement):
        return self._zip_measurements([measurement])

    @flask_login.login_required
    def route_download_logs(self):
        self.logger.debug("Download Logs.")
        return self._zip_logs()

    @flask_login.login_required
    def route_batch_list(self):
        data = request.json
        batch_id = self._batch_id_counter
        self._batch_id_counter += 1
        self._batch_measurement_names[batch_id] = data['measurement_names']
        self.logger.debug("Submit Batch for download: " + str(data['measurement_names']))
        return jsonify({'batch_id': batch_id})

    @flask_login.login_required
    def route_download_batch(self, batch_id):
        # get measurement names from batch dict
        measurement_names = self._batch_measurement_names[int(batch_id)]

        # delete batch from dict
        del self._batch_measurement_names[int(batch_id)]

        # zip measurements and return response
        return self._zip_measurements(measurement_names)

    def _zip_measurements(self, measurement_list):
        # holds a list of files to zip
        files = self._file_api.get_measurement_files(measurement_list)
        zip_files = []
        path = self._data_dir

        # iterate files from batch files and append to zip_files if file is present
        for file_name in files:
            file_path = os.path.join(path, file_name)
            if os.path.exists(file_path):
                zip_files.append({'fs': os.path.join(path, file_name), 'n': file_name})

        # make sure there is at least one file selected
        if len(zip_files) == 0:
            return jsonify({"batch-download": 'No files selected.'})

        # create zipfly object for zip_files list
        zfly = zipfly.ZipFly(paths=zip_files)

        # get generator from zipfly
        generator = zfly.generator()

        # make and return response for generator
        response = make_response(generator)
        response.timeout = None
        response.headers['mimetype'] = 'application/zip'
        return response

    def _zip_logs(self):
        # holds a list of files to zip
        files = self._file_api.get_log_files()
        zip_files = []
        path = self._logs_dir

        # iterate files from batch files and append to zip_files if file is present
        for file_name in files:
            file_path = os.path.join(path, file_name)
            if os.path.exists(file_path):
                zip_files.append({'fs': os.path.join(path, file_name), 'n': file_name})

        # make sure there is at least one file selected
        if len(zip_files) == 0:
            return jsonify({"batch-download": 'No files selected.'})

        # create zipfly object for zip_files list
        zfly = zipfly.ZipFly(paths=zip_files)

        # get generator from zipfly
        generator = zfly.generator()

        # make and return response for generator
        response = make_response(generator)
        response.timeout = None
        response.headers['mimetype'] = 'application/zip'
        return response

    @flask_login.login_required
    def route_remove_measurements(self):
        data = request.json
        result = True

        for m in data['measurements']:
            result |= self._file_api.remove_measurement(m)

        return jsonify({
            'response': result
        })

    @flask_login.login_required
    def route_system_command(self):
        data = request.json
        cmd = data['cmd']
        return jsonify(self._controller_api.send_system_command(cmd))

    @flask_login.login_required
    def route_shutdown(self):
        self._shutdown_queue.put("shutdown")
        return jsonify({
            'response': 'ok'
        })

    def shutdown(self):
        self._server.shutdown()
        self.logger.info("Flask shutdown.")
