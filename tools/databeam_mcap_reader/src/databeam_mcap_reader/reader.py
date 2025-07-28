import importlib.resources
import io
import re
import platform
import subprocess
import time
import sys
from typing import Optional, Iterator
from pathlib import Path
import logging

import numpy as np
import mcap.reader
from mcap.reader import make_reader

try:
    import orjson as json
except ImportError:
    import json

try:
    from ._core import parse_mcap
except ImportError:
    # Fallback import for development builds
    try:
        sys.path.append(str(Path(__file__).absolute().parent.parent.parent / 'build_dev'))
        from _core import parse_mcap
    except ImportError:
        # If C++ module is not available, define a placeholder
        def parse_mcap(*args, **kwargs):
            raise ImportError("C++ module '_core' is not available. Please ensure the package was built correctly.")

# Define what should be publicly available from this module
__all__ = ['McapTopic', 'McapReader', 'get_mcap_binary']

logger = logging.getLogger("databeam_mcap")
logger.setLevel(logging.DEBUG)

backup_dir_name = 'bak_recovery'


def get_mcap_binary(check_version: bool = False) -> Path:
    if platform.system() == "Windows":
        mcap_bin_name = "mcap_cli.exe"
    elif platform.system() == "Linux":
        mcap_bin_name = "mcap_cli"
    else:
        raise RuntimeError("Unsupported platform.")
    try:
        with importlib.resources.as_file(importlib.resources.files("databeam_mcap_reader") / mcap_bin_name) as bin_path:
            mcap_cli_path = Path(bin_path)
            if not mcap_cli_path.exists():
                raise FileNotFoundError
    except (ModuleNotFoundError, FileNotFoundError):
        mcap_cli_path = Path(__file__).parent.parent.parent / mcap_bin_name

    # check if executable exists
    if not mcap_cli_path.exists():
        raise RuntimeError(f"MCAP cli not found in {mcap_cli_path}.")

    if check_version:
        current_version = subprocess.check_output([mcap_cli_path.absolute(), "version"]).decode().strip()
        logger.debug(f'MCAP CLI version: {current_version}')
    return mcap_cli_path.absolute()


class McapTopic:
    def __init__(self, reader: mcap.reader.McapReader, mcap_path: Path, topic_key: int, str_limit: int = 80):
        self._reader = reader
        self._mcap_path = mcap_path
        self._mcap_folder = mcap_path.parent
        self._topic_key = topic_key
        self._topic = self._reader.get_summary().channels[topic_key].topic
        self._message_count = reader.get_summary().statistics.channel_message_counts[topic_key]
        # modulo value to update progress indicator
        self._message_count_mod = int(max(self._message_count / 100, 1))
        self._schema = json.loads(reader.get_summary().schemas[topic_key].data)
        self._fields = [x.replace(".", "_") for x in self._schema['properties'].keys()]
        self._dtypes = [x['type'] for x in self._schema['properties'].values()]
        self._fields.append("ts")
        self._dtypes.append('uint')
        self._field_dtypes = {k: v for k, v in zip(self._fields, self._dtypes)}
        self._np_dtype = {'integer': np.int64,
                          'uint': np.uint64,
                          'number': np.float64,
                          'boolean': np.bool_,
                          'string': f"S{str_limit}",
                          'array': np.float64}
        self._np_struct_format = np.dtype([(x[0], self._np_dtype[x[1]]) for x in zip(self._fields, self._dtypes)])
        self._np_struct_itemsize = self._np_struct_format.itemsize
        self._message_encoding = self._reader.get_summary().channels[topic_key].message_encoding
        if self._message_encoding != 'json':
            raise Exception("Unsupported message encoding: " + self._message_encoding)
        self._data = None

    def get_fields(self):
        return self._fields

    def get_dtypes(self):
        return self._dtypes

    def get_message_count(self):
        return self._message_count

    def _print_progress(self, cnt, max_cnt):
        """
        Print progress indicator.
        @param cnt: current number of processed messages
        @return: True if all messages have been processed
        """
        # break if num messages have been stored
        if cnt >= max_cnt:
            return True
        # print progress
        if cnt % self._message_count_mod == 0:
            percent_str = str(int((cnt / max_cnt) * 100)) + "%"
            print("\r>> Loading " + self._topic + ": " + percent_str, end="", flush=True)
        return False

    def get_default_data(self, start_time_ns: int = 0, num_messages: int = -1):
        """
        The default method to convert mcap data into numpy array data.
        """
        # limit number of messages processed
        if num_messages <= -1 or self._message_count < num_messages:
            if self._message_count < num_messages:
                logger.warning(f'limiting to {self._message_count} messages '
                               f'(file does not contain {num_messages} messages)')
            num_messages = self._message_count
        data = np.zeros((num_messages,), dtype=self._np_struct_format)

        # handle special initialization besides zero values
        for k, dt in self._field_dtypes.items():
            if dt == 'number':
                data[k] = np.nan

        try:
            ret_message = parse_mcap(data, str(self._mcap_path), self._topic, start_time_ns=start_time_ns)
        except Exception as e:
            logger.error(f'ERROR: EX parse_mcap {type(e).__name__}: {e}')
            ret_message = None

        if ret_message is None or len(ret_message):
            logger.warning(f'parse_mcap returned: "{ret_message}"')
            logger.info("Falling back to Python MCAP parsing ...")
            cnt = 0
            for schema, channel, message in self._reader.iter_messages(topics=[self._topic], start_time=start_time_ns):
                data_dict = json.loads(message.data)
                data['ts'][cnt] = message.publish_time
                for k, v in data_dict.items():
                    if isinstance(v, str) and self._field_dtypes[k] == "number":
                        data[k][cnt] = 0
                    elif v is not None:
                        data[k][cnt] = v

                # increment processed message count
                cnt += 1
                if self._print_progress(cnt, num_messages):
                    break

        return data

    def get_oscilloscope_data(self, start_time_ns: int = 0, num_messages: int = -1):
        """
        A method to convert oscilloscope mcap data into numpy array data.
        The data must be shaped in the following structure and must have the following keys:
            rel_time [array] (The relative time since the oscilloscope window started)
            data1 [array]
            dataX... (as many data arrays per window of the same size)
        """
        window_size = 1
        # Get size of the first window to use for all windows in topic
        for schema, channel, message in self._reader.iter_messages(topics=[self._topic]):
            decoded_data = json.loads(message.data)
            window_size = len(decoded_data["rel_time"])
            break
        # limit number of messages processed
        if num_messages <= -1 or self._message_count < num_messages:
            if self._message_count < num_messages:
                logger.warning(f'limiting to {self._message_count} messages '
                               f'(file does not contain {num_messages} messages)')
            num_messages = self._message_count
        data_size: int = num_messages * window_size
        data = np.zeros((data_size,), dtype=self._np_struct_format)

        # counts messages
        cnt = 0

        # iterate messages up to num_messages
        for schema, channel, message in self._reader.iter_messages(topics=[self._topic], start_time=start_time_ns):
            # parse json data
            data_dict = json.loads(message.data)
            data_len = len(data_dict["rel_time"])

            # Correctly store all data types and correct publish_time with relative time of data in window
            for i in range(data_len):
                for k, v in data_dict.items():
                    data["ts"][cnt * window_size + i] = message.publish_time + data_dict["rel_time"][i]
                    if type(data_dict[k]) is list:
                        data[k][cnt * window_size + i] = data_dict[k][i]
                    else:
                        data[k][cnt * window_size + i] = data_dict[k]

            # increment processed message count
            cnt += 1
            if self._print_progress(cnt, num_messages):
                break

        return data

    def get_data(self, start_time_ns: int = 0, num_messages: int = -1):
        # store data internally, and load only once
        if self._data is not None and start_time_ns == 0 and num_messages == -1:
            return self._data

        logger.info(f'Loading {str(num_messages) if num_messages > 0 else 'all '} messages from "{self._topic}"')
        start_time = time.time()
        # create numpy structured array holding fields and timestamp
        if "oscilloscope" in self._topic:
            parsed_data = self.get_oscilloscope_data(start_time_ns=start_time_ns, num_messages=num_messages)
        else:
            parsed_data = self.get_default_data(start_time_ns=start_time_ns, num_messages=num_messages)

        # finished loading
        print('')  # clear the ">> Loading" line
        logger.info(f'Loaded "{self._topic}": 100% in {(time.time() - start_time):.2f} seconds.')

        # return data dict
        if start_time_ns == 0 and num_messages == -1:
            self._data = parsed_data
        return parsed_data

    def get_data_chunked(self, chunk_size_megabytes: int) -> Iterator:
        # fetch single row to estimate chunk size
        _data = None
        _loaded_messages = 0
        _chunk_size = int((max(1, chunk_size_megabytes) * 1024 * 1024) // self._np_struct_itemsize)
        logger.info(f'Chunk size: {_chunk_size} messages '
                    f'({_chunk_size * self._np_struct_itemsize / 1024 / 1024:.2f} MB)')
        while _loaded_messages < self._message_count:
            if _loaded_messages + _chunk_size > self._message_count:
                _chunk_size = self._message_count - _loaded_messages
            next_ts = 0 if _data is None else _data['ts'][-1] + 1
            _data = self.get_data(start_time_ns=next_ts, num_messages=_chunk_size)
            _loaded_messages += _chunk_size
            yield _data


class McapReader:
    def __init__(self, str_limit: int = 80):
        """
        Reader class for reading an MCAP file
        :param str_limit: maximum allowed string length in pre-allocated numpy array (default: 80 characters)
        """
        self._mcap_file: Optional[io.BufferedReader] = None
        self._reader: Optional[mcap.reader.McapReader] = None
        self._mcap_topics = {}
        self._topic_lut = {}
        self._mcap_path = None
        self._str_limit = str_limit

    def __del__(self):
        self.close()

    def open(self, mcap_path: str):
        self._mcap_path = Path(mcap_path)

        try:
            self._mcap_file = open(self._mcap_path, "rb")
            self._reader = make_reader(self._mcap_file)
            summary = self._reader.get_summary()
        except Exception as e:
            logger.error(f'Failed to read MCAP file "{self._mcap_path.name}" {type(e).__name__}: {e}')
            self._reader = None
            self._mcap_file.close()
            self._recover_mcap()
            summary = None

        if summary is None:
            try:
                self._mcap_file = open(self._mcap_path, "rb")
                self._reader = make_reader(self._mcap_file)
                summary = self._reader.get_summary()
            except Exception as e:
                logger.error(f'Failed to read MCAP after recovery "{self._mcap_path.name}" {type(e).__name__}: {e}')
                raise IOError('Failed to read and recover MCAP file')

        for k, v in summary.channels.items():
            try:
                self._mcap_topics[k] = McapTopic(reader=self._reader, mcap_path=self._mcap_path, topic_key=k,
                                                 str_limit=self._str_limit)
                self._topic_lut[v.topic] = k
            except KeyError:
                logger.warning(f'Empty topic "{v.topic}" found in MCAP file "{self._mcap_path}"')

    def close(self):
        if self._mcap_file is not None:
            self._mcap_file.close()
            self._reader = None

    def _recover_mcap(self):
        logger.info(f'Recovering broken MCAP file "{self._mcap_path}"')
        mcap_bin = get_mcap_binary()
        correct_file_name = None
        if self._mcap_path.stat().st_size == 0:
            # if file is empty, still move to backup-dir (avoid repeated recovery attempts)
            logger.warning(f'mcap file is empty: {self._mcap_path.name}')
        else:
            if re.search(r'.*\.part[0-9]+\.mcap', self._mcap_path.name):
                # unfinished databeam file
                correct_file_name = (self._mcap_path.parent /
                                     Path(re.sub(r'\.part[0-9]+\.mcap', '.mcap', self._mcap_path.name)))
            else:
                # filename does not indicate a problem
                correct_file_name = (self._mcap_path.parent /
                                     Path(re.sub(r'.mcap', '_recovered.mcap', self._mcap_path.name)))

            if correct_file_name.is_file():
                logger.warning(f'recovered file already exists: {correct_file_name.name}')
                return
            # run mcap recover
            time_start = time.time()
            cmd = [mcap_bin, "--strict-message-order", "recover", self._mcap_path.absolute(),
                   "-o", correct_file_name.absolute()]
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            success_indicated = False
            for line in process.stdout:
                output = line.decode("utf-8").strip()
                logger.info(f'MCAP-CLI>> {output}')
                if 'Recovered' in output:
                    success_indicated = True  # workaround when return code is not 0 but recovery worked
            process.stdout.close()
            process.wait()
            if process.returncode != 0 and not success_indicated:
                logger.error(f'mcap recover failed after {time.time() - time_start:.2f} seconds')
                if correct_file_name.is_file():
                    correct_file_name.unlink()
                return
            logger.info(f'mcap recover took {time.time() - time_start:.2f} seconds. ')

        # make sure backup dir exists
        if not (self._mcap_path.parent / backup_dir_name).is_dir():
            (self._mcap_path.parent / backup_dir_name).mkdir(parents=True)
        # move mcap file to backup-dir
        self._mcap_path.rename(self._mcap_path.parent / backup_dir_name / (self._mcap_path.name + '.bak'))

        # rename recovered mcap file
        if correct_file_name:
            correct_file_name.rename(self._mcap_path)

    def get_structure(self):
        s = {}
        for topic in self.get_topics():
            s[topic] = {'fields': self._mcap_topics[self._topic_lut[topic]].get_fields(),
                        'dtypes': self._mcap_topics[self._topic_lut[topic]].get_dtypes(),
                        'message_count': self._mcap_topics[self._topic_lut[topic]].get_message_count()}
        return s

    def get_topics(self):
        return [x for x in self._topic_lut.keys()]

    def get_total_message_count(self):
        return self._reader.get_summary().statistics.message_count

    def get_data_list(self, topic: str):
        return self._mcap_topics[self._topic_lut[topic]].get_data_list()

    def get_data(self, topic: str, start_time_ns: int = 0, num_messages: int = -1):
        return self._mcap_topics[self._topic_lut[topic]].get_data(start_time_ns=start_time_ns,
                                                                  num_messages=num_messages)

    def get_all_data(self):
        data = {}
        for topic in self.get_topics():
            data[topic] = self.get_data(topic)
        return data

    def get_data_chunked(self, topic: str, chunk_size_megabytes: int) -> Iterator:
        return self._mcap_topics[self._topic_lut[topic]].get_data_chunked(chunk_size_megabytes)

    def print_info(self) -> str:
        info = "MCAP Info:\n"
        info += "  Total Messages: " + str(self.get_total_message_count()) + "\n"
        info += "  Topics:\n"

        for topic in self.get_topics():
            try:
                t = self._mcap_topics[self._topic_lut[topic]]
                info += "    " + topic + ":\n"
                info += "      Messages: " + str(t.get_message_count()) + "\n"
                info += "      Fields: " + str(t.get_fields()) + "\n"
                info += "      Types: " + str(t.get_dtypes()) + "\n"
            except KeyError:
                info += "    " + topic + ":\n"
                info += "      Messages: 0\n"

        print(info)
        return info


if __name__ == '__main__':
    # logging.basicConfig(level=logging.DEBUG)
    logging.basicConfig(format='%(asctime)s %(levelname)-7s | %(message)s', level=logging.DEBUG)

    # open mcap file and print info
    mcap_reader = McapReader()
    mcap_reader.open("../../testdata_multi_measurement/dummy_json.mcap")
    mcap_reader.print_info()

    # get data
    # module_data = mcap_reader.get_data("testtopic")
    # module_data = mcap_reader.get_all_data()

    # module_data = mcap_reader.get_data("testtopic", start_time_ns=0, num_messages=-1)

    topic_name = next(iter(mcap_reader.get_structure()))  # get first module name / topic
    logger.info(f'Loading topic "{topic_name}"')
    loaded_messages = 0
    for chunk in mcap_reader.get_data_chunked(topic_name, chunk_size_megabytes=100):
        loaded_messages += chunk.size
        logger.info(f'got {chunk.size} messages')

    # print(module_data["testtopic"])

    # print('')
    # module_data = mcap_reader.get_data('testtopic', start_time_ns=0, num_messages=2)
    # print(module_data)
    # print('')
    # module_data = mcap_reader.get_data('testtopic', start_time_ns=module_data['ts'][-1] + 1, num_messages=3)
    # print(module_data)

    # close mcap reader
    mcap_reader.close()
