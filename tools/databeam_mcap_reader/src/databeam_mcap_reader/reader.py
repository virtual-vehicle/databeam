import importlib.resources
import io
import re
import platform
import subprocess
import time
import sys
import traceback
from typing import Optional, Iterator, List, Dict
from pathlib import Path
import logging
from datetime import datetime, timezone

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


def type_name(v):
    if isinstance(v, bool):   return "boolean"
    if isinstance(v, int):    return "integer"  # there is no "uint" in python
    if isinstance(v, float):  return "number"
    if isinstance(v, str):    return "string"
    if isinstance(v, list):   return f"array/{type_name(v[0])}"
    if isinstance(v, dict):   return "dict"
    if v is None:             return "null"
    return type(v).__name__


class McapTopic:
    def __init__(self, reader: mcap.reader.McapReader, mcap_path: Path, topic_key: int, str_limit: int = 80):
        summary = reader.get_summary()
        message_encoding = summary.channels[topic_key].message_encoding
        if message_encoding != 'json':
            raise Exception("Unsupported message encoding: " + message_encoding)
        self._reader = reader
        self._mcap_path = mcap_path
        self._topic_key = topic_key
        self.topic = summary.channels[topic_key].topic
        if topic_key in summary.statistics.channel_message_counts:
            self._message_count = summary.statistics.channel_message_counts[topic_key]
        else:
            self._message_count = 0
        # modulo value to update progress indicator
        self._message_count_mod = int(max(self._message_count / 100, 1))

        self._np_dtype = {'number': np.float64,
                          'integer': np.int64,
                          'uint': np.uint64,
                          'boolean': np.bool_,
                          'string': f"S{str_limit}",
                          'array': np.ndarray,  # clarify type of items!
                          }

        self._fields = []  # filled in self._parse_schema
        self._dtypes = []  # filled in self._parse_schema
        self._np_struct_format = np.dtype([])  # filled in self._parse_schema
        schema = json.loads(summary.schemas[topic_key].data)
        self._parse_schema(schema['properties'])

        self._np_struct_itemsize = self._np_struct_format.itemsize
        self._data = None

    def _parse_schema(self, schema: dict) -> None:  # -> Tuple[List[str], List[str], np.dtype]:
        # add timestamp column
        self._fields = ['ts']
        self._dtypes = ['uint']
        np_dtypes = [(self._fields[0], self._np_dtype[self._dtypes[0]])]

        # one array containing multiple fields (lists) is allowed - they must be the same length
        contains_array: List[str] = []

        # map field names to numpy dtypes, ignoring unsupported dtypes
        for k, dt in schema.items():
            if k == 'ts':  # ignore timestamp field in schema
                continue
            field_name = k.replace(".", "_")
            d_type = dt['type']
            if d_type not in self._np_dtype:
                logger.warning(f'Unsupported dtype: "{d_type}" - skipping field "{k}"')
                continue
            if d_type == 'array':
                contains_array.append(k)  # gets handled separately below
                continue
            self._fields.append(field_name)
            self._dtypes.append(d_type)
            np_dtypes.append((field_name, self._np_dtype[d_type]))

        # handle array entries: find type
        array_dtypes = []
        array_length = None
        for k in contains_array:
            field_name = k.replace(".", "_")
            array_item_type = None
            try:
                # may not exist in old mcap files. alternatively parse from first message
                array_item_type = schema[k]['items']['type']
            except KeyError:
                # array item type not specified in schema
                logger.warning(f'Array item type not specified in schema - "{k}", falling back to detecting type')

            try:
                _, _, message = next(self._reader.iter_messages(topics=[self.topic]))
            except StopIteration:
                logger.warning(f'Topic "{self.topic}" does not contain data. Aborting array parsing')
                array_dtypes = []
                break

            decoded_data = json.loads(message.data)
            if k in decoded_data:
                array_item_type_parsed = type_name(decoded_data[k][0])
            else:
                logger.warning(f'Array field "{k}" not found in message data - skipping field')
                continue
            if array_length is None:
                array_length = len(decoded_data[k])
            else:
                if len(decoded_data[k]) != array_length:
                    logger.warning(f'Array field "{k}" has different length than other arrays - aborting array parsing')
                    array_dtypes = []
                    break
            # only use parsed type if schema type is not specified
            if array_item_type is None:
                array_item_type = array_item_type_parsed
            if array_item_type != array_item_type_parsed:
                logger.warning(f'Array item type mismatch for field "{k}": '
                               f'schema: {array_item_type}, parsed: {array_item_type_parsed}')

            if array_item_type is None or array_item_type not in self._np_dtype:
                logger.warning(f'Failed to detect array item type for field "{k}", skipping field')
                continue
            array_dtypes.append((field_name, self._np_dtype[array_item_type]))

        if len(array_dtypes) and array_length is not None:
            self._fields.append('array')
            self._dtypes.append('array')
            np_dtypes.append(('array', (np.dtype(array_dtypes), (array_length,))))

        self._np_struct_format = np.dtype(np_dtypes)

    def get_numpy_dtypes(self):
        return [self._np_dtype[d] for d in self._dtypes]

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
            if logger.level == logging.DEBUG:
                print("\r>> Loading " + self.topic + ": " + percent_str, end="", flush=True)
        return False

    def get_data(self, start_time_ns: int = 0, num_messages: int = -1) -> Optional[np.ndarray]:
        # store data internally, and load only once
        if (self._data is not None and start_time_ns == 0 and
                (num_messages == -1 or num_messages == self._message_count)):
            return self._data

        logger.info(f'Loading {str(num_messages) if num_messages > 0 else "all"} messages from "{self.topic}"')
        start_time = time.time()

        # limit number of messages processed
        if num_messages <= -1 or self._message_count < num_messages:
            if self._message_count < num_messages:
                logger.warning(f'limiting to {self._message_count} messages '
                               f'(file does not contain {num_messages} messages)')
            num_messages = self._message_count

        # create numpy structured array holding fields and timestamp
        data = np.zeros((num_messages,), dtype=self._np_struct_format)

        # handle special initialization besides zero values
        for k in self._np_struct_format.fields:
            if self._np_struct_format[k] == np.float64:
                data[k] = np.nan

        try:
            ret_message = parse_mcap(data, str(self._mcap_path), self.topic, start_time_ns=start_time_ns,
                                     quiet=False if logger.level == logging.DEBUG else True)
        except Exception as e:
            logger.error(f'ERROR: EX parse_mcap {type(e).__name__}: {e}')
            ret_message = None

        if ret_message is None or len(ret_message):
            logger.warning(f'parse_mcap returned: "{ret_message}"')
            if 'array' in self._dtypes:
                logger.error('Array parsing failed and fallback is not available')
                return None
            logger.info("Falling back to Python MCAP parsing ...")
            cnt = 0
            for schema, channel, message in self._reader.iter_messages(topics=[self.topic], start_time=start_time_ns):
                data_dict = json.loads(message.data)
                data['ts'][cnt] = message.publish_time
                for k, v in data_dict.items():
                    if isinstance(v, str) and self._np_struct_format[k] == np.float64:
                        data[k][cnt] = 0
                    elif v is not None:
                        data[k][cnt] = v

                # increment processed message count and check if we need to abort
                cnt += 1
                if self._print_progress(cnt, num_messages):
                    break

        # finished loading
        if logger.level == logging.DEBUG:
            print('')  # clear the ">> Loading" line
        logger.info(f'Loaded "{self.topic}": '
                    f'{"100%" if num_messages == -1 or num_messages == self._message_count else
                    f"{num_messages} messages"} in {(time.time() - start_time):.2f} seconds.')

        # return data dict
        if start_time_ns == 0 and num_messages == self._message_count:
            self._data = data
        return data

    def get_data_chunked(self, chunk_size_megabytes: int) -> Iterator:
        # fetch single row to estimate chunk size
        _data: Optional[np.ndarray] = None
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
        self.time_start_ns = 0
        self.time_end_ns = 0

    def __del__(self):
        self.close()

    def open(self, mcap_path: str):
        self.close()
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

        # recovery was attempted - check again
        if summary is None:
            try:
                self._mcap_file = open(self._mcap_path, "rb")
                self._reader = make_reader(self._mcap_file)
                summary = self._reader.get_summary()
            except Exception as e:
                logger.error(f'Failed to read MCAP after recovery "{self._mcap_path.name}" {type(e).__name__}: {e}')
                raise IOError('Failed to read and recover MCAP file')

        self.time_start_ns = summary.statistics.message_start_time
        self.time_end_ns = summary.statistics.message_end_time

        for k, v in summary.channels.items():
            try:
                self._mcap_topics[k] = McapTopic(reader=self._reader, mcap_path=self._mcap_path, topic_key=k,
                                                 str_limit=self._str_limit)
            except Exception as e:
                logger.error(f'Failed to create MCAP topic "{v.topic}" {type(e).__name__}: {e}\n'
                             f'{traceback.format_exc()}')
                raise e
            try:
                self._topic_lut[v.topic] = k
            except KeyError:
                logger.warning(f'Empty topic "{v.topic}" found in MCAP file "{self._mcap_path}"')

    def close(self):
        if self._mcap_file is not None:
            self._mcap_file.close()
        self._mcap_file = None
        self._reader = None
        self._mcap_topics = {}
        self._topic_lut = {}
        self._mcap_path = None

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
        for topic in self.get_topic_names():
            s[topic] = {'fields': self._mcap_topics[self._topic_lut[topic]].get_fields(),
                        'dtypes': self._mcap_topics[self._topic_lut[topic]].get_dtypes(),
                        'message_count': self._mcap_topics[self._topic_lut[topic]].get_message_count()}
        return s

    def get_topic_names(self) -> List[str]:
        return [x for x in self._topic_lut.keys()]

    def get_topics(self) -> Dict[str, McapTopic]:
        return {topic.topic: topic for topic in self._mcap_topics.values()}

    def get_total_message_count(self):
        return self._reader.get_summary().statistics.message_count

    def get_data_list(self, topic: str):
        return self._mcap_topics[self._topic_lut[topic]].get_data_list()

    def get_data(self, topic: str, start_time_ns: int = 0, num_messages: int = -1):
        return self._mcap_topics[self._topic_lut[topic]].get_data(start_time_ns=start_time_ns,
                                                                  num_messages=num_messages)

    def get_all_data(self):
        data = {}
        for topic in self.get_topic_names():
            data[topic] = self.get_data(topic)
        return data

    def get_data_chunked(self, topic: str, chunk_size_megabytes: int) -> Iterator:
        return self._mcap_topics[self._topic_lut[topic]].get_data_chunked(chunk_size_megabytes)

    def get_info_string(self) -> str:
        info = "MCAP Info:\n"
        info += "  Start Time: " + str(self.time_start_ns) + "\n"
        info += "  End Time: " + str(self.time_end_ns) + "\n"
        info += "  Total Messages: " + str(self.get_total_message_count()) + "\n"
        info += "  Topics:\n"

        for topic in self.get_topic_names():
            try:
                t = self._mcap_topics[self._topic_lut[topic]]
                info += "    " + topic + ":\n"
                info += "      Messages: " + str(t.get_message_count()) + "\n"
                info += "      Fields: " + str(t.get_fields()) + "\n"
                info += "      Types: " + str(t.get_dtypes()) + "\n"
            except KeyError:
                info += "    " + topic + ":\n"
                info += "      Messages: 0\n"
        return info


if __name__ == '__main__':
    loglevel = logging.DEBUG
    logging.basicConfig(format='%(asctime)s %(levelname)-7s | %(message)s', level=loglevel)
    logger.setLevel(loglevel)

    # open mcap file and print info
    mcap_reader = McapReader()
    # mcap_reader.open("../../testdata_multi_measurement/dummy_json.mcap")
    mcap_reader.open("../../testdata_multi_measurement/dummy_small_json.mcap")
    print(mcap_reader.get_info_string())

    start_time_ns = mcap_reader.time_start_ns
    end_time_ns = mcap_reader.time_end_ns
    for t in [('Start', start_time_ns), ('Stop', end_time_ns)]:
        dt = datetime.fromtimestamp(t[1] / 1e9, tz=timezone.utc)
        formatted = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"
        print(f"{t[0]} time {t[1]}: {dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3] + " UTC"}")

    message_count = mcap_reader.get_total_message_count()
    structure = mcap_reader.get_structure()
    topic_names = mcap_reader.get_topic_names()
    all_topics = mcap_reader.get_topics()

    # get data
    module_data = mcap_reader.get_data(topic_names[0])
    module_data = mcap_reader.get_all_data()

    # module_data = mcap_reader.get_data("testtopic", start_time_ns=0, num_messages=-1)

    topic_name = topic_names[0]  # get first module name / topic
    selected_topic = all_topics[topic_name]
    topic_dtypes = selected_topic.get_dtypes()
    topic_fields = selected_topic.get_fields()
    topic_numpy_dtypes = selected_topic.get_numpy_dtypes()

    logger.info(f'Fetching topic "{topic_name}" in chunked mode')
    loaded_messages = 0
    for chunk in mcap_reader.get_data_chunked(topic_name, chunk_size_megabytes=100):
        if chunk is None:
            logger.error('Failed to load data chunk')
            break
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
