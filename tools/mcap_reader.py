import io
import os
import shutil
import subprocess
import time
import sys
import platform
from typing import Optional, List

import mcap.reader
from mcap.reader import make_reader
import mcap.summary
import numpy as np
from pathlib import Path
try:
    import orjson as json
except ImportError:
    import json

NP_BUFFER_COMPRESSION = True

def get_mcap_cli_name():
    if platform.system() == "Windows":
        mcap_cli_path = 'mcap_cli.exe'
    elif platform.system() == "Linux":
        mcap_cli_path = './mcap_cli'
    else:
        raise RuntimeError("Unsupported platform.")
    return mcap_cli_path

class McapTopic:
    def __init__(self, reader: mcap.reader.McapReader, mcap_path: Path, topic_key: int, numpy_buffering=True):
        self._reader = reader
        self._numpy_buffering = numpy_buffering
        self._mcap_path = mcap_path
        self._mcap_folder = mcap_path.parent
        self._numpy_dir = self._mcap_folder / "numpy"
        self._topic_key = topic_key
        self._topic = self._reader.get_summary().channels[topic_key].topic
        self._message_count = reader.get_summary().statistics.channel_message_counts[topic_key]
        self._schema = json.loads(reader.get_summary().schemas[topic_key].data)
        self._fields = [x.replace(".", "_") for x in self._schema['properties'].keys()]
        self._dtypes = [x['type'] for x in self._schema['properties'].values()]
        self._fields.append("ts")
        self._dtypes.append('uint')
        self._field_dtypes = {k: v for k, v in zip(self._fields, self._dtypes)}
        self._np_dtype = {'integer': np.int64, 'uint': np.uint64, 'number': np.float64, 'boolean': np.bool_,
                          'string': "S80", 'array': np.float64}
        self._message_encoding = self._reader.get_summary().channels[topic_key].message_encoding
        if self._message_encoding != 'json':
            raise Exception("Unsupported message encoding: " + self._message_encoding)

    def get_fields(self):
        return self._fields

    def get_dtypes(self):
        return self._dtypes

    def get_message_count(self):
        return self._message_count

    def _load_data_npy(self):
        if not self._numpy_buffering:
            return None

        # try to load cached data from disk, either compressed (npz) or uncompressed (npy)
        np_ftypes = ['.npy', '.npz']
        for np_ftype in np_ftypes:
            np_file = self._numpy_dir / (self._topic + np_ftype)
            if os.path.exists(np_file):
                time_start = time.time()
                print(f'Loading numpy file: {np_file.name}', end="")
                with open(np_file, 'rb') as f:
                    a = np.load(f)
                    ret = a['data'] if np_ftype == '.npz' else a
                    print(f'\rLoading numpy file: {np_file.name} done: {round(time.time() - time_start, 2)} s')
                    return ret

        return None

    def get_data_list(self):
        """
        Returns its topic data as a dictionary of python lists.
        """
        list_data = {}
        np_data = self.get_data()
        print("Converting to list...", end="")
        transposed_data = np.vstack([np_data[x] for x in np_data.dtype.names])
        for idx, fieldname in enumerate(np_data.dtype.names):
            list_data[fieldname] = transposed_data[idx].tolist()
        print(" finished.")
        return list_data

    def stream_mcap_json(self, topics: List, mcap_cli_path=''):
        # use the official mcap cli tool to stream mcap data
        if mcap_cli_path == '':
            mcap_cli_path = get_mcap_cli_name()

        # check if executable exists
        if shutil.which(mcap_cli_path) is None:
            #print(f"[MCAP Reader] {mcap_cli_path} not found. Use install_mcap_cli.py to install the mcap cli tool.")
            raise RuntimeError("MCAP cli not found.")

        cmd = [mcap_cli_path, "--strict-message-order", "cat", self._mcap_path, "--json", "--topics", ",".join(topics)]
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE)

        for line in process.stdout:
            try:
                msg = json.loads(line)
                yield msg
            except json.JSONDecodeError as e:
                print(f"\nJSON decode error ({line}): ", e)
                raise e

        process.stdout.close()
        process.wait()

    def get_default_data(self, np_struct_format):
        """
        The default method to convert mcap data into numpy array data.
        """
        data = np.zeros((self._message_count,), dtype=np_struct_format)

        # counts messages
        cnt = 0

        # modulo value to update progress indicator
        mod = int(max(self._message_count / 100, 1))

        # create a dict with numpy default values
        proto_dict = {}
        for k, v in np_struct_format:
            if self._field_dtypes[k] == "string":
                proto_dict[k] = ''
            elif self._field_dtypes[k] == "integer":
                # smallest possible int
                proto_dict[k] = np.iinfo(self._np_dtype[self._field_dtypes[k]]).min  # TODO define 'None' value
            elif self._field_dtypes[k] == "uint":
                proto_dict[k] = 0
            elif self._field_dtypes[k] == "number":
                proto_dict[k] = float("nan")
            else:
                raise Exception("Unknown dtype: " + self._field_dtypes[k])

        # iterate messages up to num_messages
        try:
            for message in self.stream_mcap_json([self._topic]):
                data_dict = proto_dict.copy()
                # TODO CLI tool reports imprecise times (float vs. int)
                #     --> cli: float (s, 1751301079.6529176) ... mcap: int (ns, 1751301079652917736)
                message['data']['ts'] = int(message['publish_time'] * 1e9)
                # missing values are automatically kept at default values from proto_dict
                data_dict.update(message['data'])

                try:
                    data[cnt] = tuple(data_dict.values())
                except TypeError:
                    print(f"\nTypeError ({data_dict})")
                    # handle None-values
                    if None in data_dict.values():
                        data_dict = proto_dict.copy()
                        data_dict.update({k: v for k, v in message['data'].items() if v is not None})
                        data[cnt] = tuple(data_dict.values())

                # increment processed message count
                cnt += 1

                # break if num messages have been stored
                if cnt >= self._message_count:
                    break

                # print progress
                if cnt % mod == 0:
                    percent_str = str(int((cnt / self._message_count) * 100)) + "%"
                    print("\rLoading " + self._topic + ": " + percent_str, end="")
        except json.JSONDecodeError as e:
            data = None
        except RuntimeError as e:
            data = None

        if data is None:
            print("Falling back to slow MCAP parsering ...")
            data = np.zeros((self._message_count,), dtype=np_struct_format)
            cnt = 0
            for schema, channel, message in self._reader.iter_messages(topics=[self._topic]):
                data_dict = json.loads(message.data)
                data['ts'][cnt] = message.publish_time
                for k, v in data_dict.items():
                    if isinstance(v, str) and self._field_dtypes[k] == "number":
                        data[k][cnt] = 0
                    else:
                        data[k][cnt] = v
                # increment processed message count
                cnt += 1
                # break if num messages have been stored
                if cnt >= self._message_count:
                    break
                # print progress
                if cnt % mod == 0:
                    percent_str = str(int((cnt / self._message_count) * 100)) + "%"
                    print("\rLoading " + self._topic + ": " + percent_str, end="")

        return data

    def get_oscilloscope_data(self, np_struct_format):
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
        data_size: int = self._message_count * window_size
        data = np.zeros((data_size,), dtype=np_struct_format)

        # counts messages
        cnt = 0

        # modulo value to update progress indicator
        mod = int(max(self._message_count / 100, 1))

        # iterate messages up to num_messages
        for message in self.stream_mcap_json(topics=[self._topic]):
            # parse json data
            data_dict = json.loads(message['data'])
            publish_time = int(message['publish_time'] * 1e9)
            data_len = len(data_dict["rel_time"])

            # Correctly store all data types and correct publish_time with relative time of data in window
            for i in range(data_len):
                for k, v in data_dict.items():
                    data["ts"][cnt * window_size + i] = publish_time + data_dict["rel_time"][i]
                    if type(data_dict[k]) is list:
                        data[k][cnt * window_size + i] = data_dict[k][i]
                    else:
                        data[k][cnt * window_size + i] = data_dict[k]

            # increment processed message count
            cnt += 1

            # break if num messages have been stored
            if cnt >= self._message_count:
                break

            # print progress
            if cnt % mod == 0:
                percent_str = str(int((cnt / self._message_count) * 100)) + "%"
                print("\rLoading " + self._topic + ": " + percent_str, end="")

        return data

    def get_data(self):
        # try to load cached data from disk
        temp_data = self._load_data_npy()

        # return given cached data
        if temp_data is not None:
            print("Loading " + self._topic + ": 100% (cached numpy file)")
            return temp_data

        # create numpy structured array holding fields and timestamp
        np_struct_format = [(x[0], self._np_dtype[x[1]]) for x in zip(self._fields, self._dtypes)]
        np_struct_format.append(('ts', np.uint64))

        # Remove duplicate ts field if present in mcap schema
        ts_fields = []
        for idx, field in enumerate(np_struct_format):
            if field[0] == "ts":
                ts_fields.append(idx)
        if len(ts_fields) > 1:
            np_struct_format.pop(ts_fields[0])

        if "oscilloscope" in self._topic:
            data = self.get_oscilloscope_data(np_struct_format)
        else:
            data = self.get_default_data(np_struct_format)

        # print finished loading
        print("\rLoading " + self._topic + ": 100%")

        # store numpy data for topic as numpy file
        if self._numpy_buffering:
            # create numpy folder if not exists
            if not os.path.exists(self._numpy_dir):
                os.mkdir(self._numpy_dir)

            if NP_BUFFER_COMPRESSION:
                np_file = self._numpy_dir / (self._topic + ".npz")
                print('saving numpy file: ' + np_file.name)
                with open(np_file, 'wb') as f:
                    np.savez_compressed(f, data=data)
            else:
                np_file = self._numpy_dir / (self._topic + ".npy")
                print('saving numpy file: ' + str(np_file))
                with open(np_file, 'wb') as f:
                    np.save(f, data)

        # return data dict
        return data


class McapReader:
    def __init__(self, numpy_buffering=True):
        self._mcap_file: Optional[io.BufferedReader] = None
        self._reader: Optional[mcap.reader.McapReader] = None
        self._mcap_topics = {}
        self._topic_lut = {}
        self._mcap_path = None
        self._numpy_buffering = numpy_buffering

        # get mcap cli path
        #mcap_cli_path = get_mcap_cli_name()

    def open(self, mcap_path: str):
        self._mcap_path = Path(mcap_path)
        self._mcap_file = open(self._mcap_path, "rb")
        self._reader = make_reader(self._mcap_file)

        for k, v in self._reader.get_summary().channels.items():
            try:
                self._mcap_topics[k] = McapTopic(reader=self._reader, mcap_path=self._mcap_path, topic_key=k,
                                                 numpy_buffering=self._numpy_buffering)
                self._topic_lut[v.topic] = k
            except KeyError:
                print(f"[Warning] Empty topic {v.topic} found.")

    def close(self):
        if self._mcap_file is not None:
            self._mcap_file.close()
            self._reader = None

    def get_topics(self):
        return [x.topic for x in self._reader.get_summary().channels.values()]

    def get_total_message_count(self):
        return self._reader.get_summary().statistics.message_count

    def get_data_list(self, topic: str):
        return self._mcap_topics[self._topic_lut[topic]].get_data_list()

    def get_data(self, topic: str):
        return self._mcap_topics[self._topic_lut[topic]].get_data()

    def print_info(self):
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


if __name__ == '__main__':
    measurement_path = "./2024-06-12_15-28-15.937_15_TestCSV"

    # open mcap file and print info
    mcap_reader = McapReader(numpy_buffering=False)
    mcap_reader = McapReader()
    mcap_reader.open(measurement_path + "/Redlab_TEMP/Redlab_TEMP.mcap")
    mcap_reader.print_info()

    # get data
    start_ts = time.time()
    #module_data = mcap_reader.get_data("ping")
    #data = mcap_reader.get_data_list("ping")
    module_data = mcap_reader.get_data("temperatures")  # TODO: add option to load all topics --> dict of struc-arrays
    print("Time: " + str(round(time.time() - start_ts, 2)) + " seconds")

    # print data
    print(len(module_data['ts']))
    #print(data.keys())

    # close mcap reader
    mcap_reader.close()
