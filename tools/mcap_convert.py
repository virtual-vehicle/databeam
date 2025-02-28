import sys
import os
import csv
import json
import time
from pathlib import Path
from typing import Optional

from mcap.reader import make_reader


class IMessageWriter:
    """
    MessageWriter interface. Derived to handle different channel topics.
    """

    def write_line(self, message, data_dict, schema, csv_writer):
        """
        Virtual function to override with a specific MessageWriter class. Defines how the
        individual messages in the mcap file are written in the csv file.
        :param message: The raw mcap message.
        :param data_dict: The dictionary converted mcap message.
        :param schema: The schema of the message.
        :param csv_writer: The csv writer reference.
        """
        raise NotImplementedError("Please use IMessageWriter to derive a specific line writer class.")

    @staticmethod
    def select_writer(topic: str):
        """
        Called to select the appropriate writer for a certain channel topic.
        :param topic: The topic to select the MessageWriter with.
        """
        if "oscilloscope" in topic:
            return OscilloscopeMessageWriter()
        else:
            return DefaultMessageWriter()


class DefaultMessageWriter(IMessageWriter):
    """
    The default line writer. Writes each value of a message into another column.
    """

    def write_line(self, message, data_dict, schema, csv_writer):
        ts = message.publish_time

        if schema.name == "foxglove.GeoJSON":
            coordinates = json.loads(data_dict['geojson'])['coordinates']
            data_dict = {'lon': coordinates[0],
                         'lat': coordinates[1]}

        csv_writer.writerow([ts] + list(data_dict.values()))


class OscilloscopeMessageWriter(IMessageWriter):
    """
    A writer specialized on oscilloscope data in shape of lists. Writes a list of values
    into a single column in different rows. A rel_time list is used to add the a time
    passed since start of the oscilloscope window to the timestamp.
    """

    def write_line(self, message, data_dict, schema, csv_writer):
        data_len = len(data_dict["rel_time"])

        for i in range(data_len):
            inject_dict = {}
            ts = int(message.publish_time) + int(data_dict["rel_time"][i])
            for key in data_dict.keys():
                if isinstance(data_dict[key], list):
                    inject_dict[key] = data_dict[key][i]
                elif key == "timestamp":
                    pass  # Leave out timestamp, since it will later be included as ts.
                else:
                    inject_dict[key] = data_dict[key]

            csv_writer.writerow([ts] + list(inject_dict.values()))


def num_messages_str(num_samples):
    if num_samples < 1000:
        return str(num_samples)
    if num_samples < 1000000:
        return str(round(num_samples / 1000, 1)) + "k"
    return str(round(num_samples / 1000000, 1)) + "M"


def elapsed_time_str(seconds):
    if seconds < 0.01:
        return str(round(seconds * 1000, 3)) + "ms"
    else:
        return str(round(seconds, 2)) + "s"


def meta_to_csv(measurement_path, module_name):
    module_meta_path = measurement_path / module_name / "module_meta.json"
    csv_path = measurement_path / module_name / "csv" / "module_meta.csv"

    if not os.path.exists(module_meta_path):
        print("[Convert] Meta data file for " + module_name + " not found - skipping")
        return
    print("[Convert] " + module_name + " meta data")

    with open(module_meta_path, "r") as f:
        meta_dict = json.load(f)
        meta_dict['module_name'] = module_name
        config_dict = json.loads(meta_dict['config'])
        del config_dict['config_properties']
        del meta_dict['config']

        # open csv file and write meta
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        with open(csv_path, "w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file)
            for k, v in meta_dict.items():
                csv_writer.writerow([k, v])
            for k, v in config_dict.items():
                csv_writer.writerow([k, v])


def mcap_to_csv(measurement_path: Path, module_name: Optional[str] = None) -> None:
    measurement_path = Path(measurement_path)
    # compute path to mcap and csv file
    if os.path.isfile(measurement_path):
        if module_name is not None:
            print("Error: module_name must be None if measurement_path is a file.")
            return
        if not measurement_path.name.endswith(".mcap"):
            print("Error: measurement_path must be a .mcap file.")
            return
        input_dir = measurement_path.parent
        mcap_path = measurement_path
    else:
        input_dir = measurement_path / module_name
        mcap_path = input_dir / (module_name + ".mcap")

    # check if file exists
    if not os.path.exists(mcap_path):
        print("[Convert] " + mcap_path.name + " not found - skipping")
        return
    print("[Convert] " + mcap_path.name)

    with open(mcap_path, "rb") as f:
        # create mcap reader
        reader = make_reader(f)

        # get list of channels
        summary = reader.get_summary()
        total_messages = summary.statistics.message_count
        schemas = list(summary.schemas.values())
        channels = [v for k, v in reader.get_summary().channels.items()]
        statistics = reader.get_summary().statistics

        if len(statistics.channel_message_counts) == 0:
            print("  No schema for mcap file found. Skipped.")
            return

        print(f'  Total Messages: {num_messages_str(total_messages)}')

        # iterate channels and log data
        for i in range(0, statistics.channel_count):
            ch = channels[i]
            print(f"    Converting schema with topic <{ch.topic}>.")

            if "camera" in ch.topic:
                print(f'\r    {ch.topic}: Skipped.')
                continue

            if ch.schema_id not in statistics.channel_message_counts:
                print("    Could not find data for schema in mcap file. Skipped.")
                print("")
                continue

            message_count = statistics.channel_message_counts[ch.schema_id]
            mod = int(max(message_count / 100, 1))

            # create csv path
            csv_path = input_dir / "csv" / (ch.topic + ".csv")
            csv_path.parent.mkdir(parents=True, exist_ok=True)

            # open csv file
            csv_file = open(csv_path, "w", newline="")
            csv_writer = csv.writer(csv_file)

            # store start time
            start_ts = time.time()
            cnt = 0
            header_written = False

            # Select line writer strategy based on schema topic
            line_writer = IMessageWriter.select_writer(ch.topic)

            # iterate messages
            for schema, channel, message in reader.iter_messages(topics=[ch.topic]):
                # parse data from json string
                data_dict = json.loads(message.data.decode('utf-8'))

                # write csv header once
                if not header_written:
                    header_written = True
                    csv_writer.writerow(['TS'] + list(data_dict.keys()))

                line_writer.write_line(message, data_dict, schemas[i], csv_writer)

                # print progress
                cnt += 1
                if cnt % mod == 0:
                    elapsed = (time.time() - start_ts) + sys.float_info.epsilon
                    msg_per_sec = cnt / elapsed
                    percent_str = str(int((cnt / message_count) * 100)) + "%"
                    time_remaining = int((message_count - cnt) / msg_per_sec)
                    print(f'\r    {ch.topic}: {percent_str}, {time_remaining}s remaining', end="")

            # close csv file
            csv_file.close()

            # print statistics
            elapsed_time_s = (time.time() - start_ts) + sys.float_info.epsilon
            elapsed_str = elapsed_time_str(elapsed_time_s)
            print(f'\r    {ch.topic}: 100% in {elapsed_str} ({int(message_count / elapsed_time_s)} Msg/s)', end="\n")


if __name__ == '__main__':
    # provide a single .mcap file or a databeam-measurement directory
    if len(sys.argv) > 1:
        measurement_arg_path = Path(sys.argv[1])
    else:
        measurement_arg_path = Path("measurements_0/2025-01-17_09-10-17.357_6_test")

    if os.path.isfile(measurement_arg_path):
        # convert single mcap file
        mcap_to_csv(measurement_arg_path)
    else:
        # convert whole measurement directory with module-directories
        dirs = os.listdir(measurement_arg_path)
        modules = [x for x in dirs if x != "meta.json"]
        print("Modules: " + str(modules) + "\n")

        # iterate all modules
        for m in modules:
            # convert mcap to csv
            mcap_to_csv(measurement_arg_path, m)
            meta_to_csv(measurement_arg_path, m)
            print("")
