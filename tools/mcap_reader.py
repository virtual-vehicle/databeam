import io
import os
import json
import time
import mcap.reader
import mcap.summary
import numpy as np
from pathlib import Path
from mcap.reader import make_reader

class McapTopic:
    def __init__(self, reader: mcap.reader.McapReader, mcap_path: Path, topic_key: int):
        self._reader = reader
        self._mcap_path = mcap_path
        self._mcap_folder = mcap_path.parent
        self._numpy_dir = self._mcap_folder / "numpy"
        self._topic_key = topic_key
        self._topic = self._reader.get_summary().channels[topic_key].topic
        self._message_count = reader.get_summary().statistics.channel_message_counts[topic_key]
        self._schema = json.loads(reader.get_summary().schemas[topic_key].data.decode('utf-8'))
        self._fields = [x.replace(".", "_") for x in self._schema['properties'].keys()]
        self._dtypes = [x['type'] for x in self._schema['properties'].values()]
        self._field_dtypes = {k: v for k,v in zip(self._fields, self._dtypes)}
        self._np_dtype = {'integer': np.int64, 'number': np.float64, 'boolean': np.bool_, "string": "S80"}

    def get_fields(self):
        return self._fields

    def get_dtypes(self):
        return self._dtypes

    def get_message_count(self):
        return self._message_count

    def _load_data_npy(self):
        np_file = self._numpy_dir / (self._topic + ".npy")

        if os.path.exists(np_file):
            with open(np_file, 'rb') as f:
                return np.load(f)

        return None

    def get_data_list(self):
        data = {x: [0] * self._message_count for x in self._fields}
        data['ts'] = [0] * self._message_count

        # counts messages
        cnt = 0

        # modulo value to update progress indicator
        mod = int(max(self._message_count / 100, 1))

        # iterate messages up to num_messages
        for schema, channel, message in self._reader.iter_messages(topics=[self._topic]):
            # parse json data
            data_dict = json.loads(message.data.decode('utf-8'))

            # store timstamp
            data['ts'][cnt] = message.publish_time

            # store fields
            for k, v in data_dict.items():
                data[k][cnt] = v

            # increment processed message count
            cnt += 1

            # print progress
            if cnt % mod == 0:
                percent_str = str(int((cnt / self._message_count) * 100)) + "%"
                print("\rLoading " + self._topic + ": " + percent_str, end="")

        # print finished loading
        print("\rLoading " + self._topic + ": 100%")

        # return data dict
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
        data = np.zeros((self._message_count, ), dtype=np_struct_format)

        # counts messages
        cnt = 0

        # modulo value to update progress indicator
        mod = int(max(self._message_count / 100, 1))

        # iterate messages up to num_messages
        for schema, channel, message in self._reader.iter_messages(topics=[self._topic]):
            # parse json data
            data_dict = json.loads(message.data.decode('utf-8'))

            # store timstamp
            data['ts'][cnt] = message.publish_time

            # store fields
            for k, v in data_dict.items():
                if self._field_dtypes[k] == "number" and isinstance(v, str):
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

        # print finished loading
        print("\rLoading " + self._topic + ": 100%")

        # create numpy file path for topic
        np_file = self._numpy_dir / (self._topic + ".npy")

        # create numpy folder if not exists
        if not os.path.exists(self._numpy_dir):
            os.mkdir(self._numpy_dir)

        # store numpy data for topic as numpy file
        with open(np_file, 'wb') as f:
            np.save(f, data)

        # return data dict
        return data


class McapReader:
    def __init__(self):
        self._mcap_file: io.BufferedReader = None
        self._reader: mcap.reader.McapReader = None
        self._mcap_topics = {}
        self._topic_lut = {}
        self._mcap_path = None

    def open(self, mcap_path: str):
        self._mcap_path = Path(mcap_path)
        self._mcap_file = open(self._mcap_path, "rb")
        self._reader = make_reader(self._mcap_file)

        for k, v in self._reader.get_summary().channels.items():
            self._mcap_topics[k] = McapTopic(self._reader, self._mcap_path, k)
            self._topic_lut[v.topic] = k

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
            t = self._mcap_topics[self._topic_lut[topic]]
            info += "    " + topic + ":\n"
            info += "      Messages: " + str(t.get_message_count()) + "\n"
            info += "      Fields: " + str(t.get_fields()) + "\n"
            info += "      Types: " + str(t.get_dtypes()) + "\n"

        print(info)

if __name__ == '__main__':
    measurement_path = "/home/michelicadm/Downloads/measurements/2024-06-12_15-28-15.937_15_TestCSV"
    #measurement_path = "/home/michelicadm/Downloads/measurements/2024-06-12_16-46-07.434_18_TestCSV"
    #measurement_path = "/home/michelicadm/Downloads/measurements/2024-06-12_16-46-07.434_18_TestCSV"

    # open mcap file and print info
    mcap_reader = McapReader()
    mcap_reader.open(measurement_path + "/REDLAB_1808_X/REDLAB_1808_X.mcap")
    mcap_reader.print_info()

    # get data
    start_ts = time.time()
    #data = mcap_reader.get_data("ping")
    #data = mcap_reader.get_data_list("ping")
    data = mcap_reader.get_data("Redlab-1808")
    print("Time: " + str(round(time.time() - start_ts, 2)) + " seconds")

    # print data
    print(len(data['ts']))
    #print(data.keys())

    # close mcap reader
    mcap_reader.close()
