Read [**DataBeam**](https://github.com/virtual-vehicle/databeam) MCAP files with ease.


This Python library provides a high performance parser - implemented in C++ - for [MCAP](https://mcap.dev/) files produced by the **DataBeam** DAQ software: [https://github.com/virtual-vehicle/databeam](https://github.com/virtual-vehicle/databeam).

**databeam_mcap_reader** only works for reading MCAP files with **JSON-encoded data** containing a **mandatory schema**.

Unfinalized or damaged MCAP files will get automatically repaired by the MCAP-CLI tool.

See official [MCAP documentation](https://mcap.dev/guides/getting-started/json) for more information.

## Usage of Reader

#### Get a reader instance:
```
import databeam_mcap_reader as mr
reader = mr.McapReader()
```

#### Open a file:
```
reader.open('path/to/file.mcap')
```

#### Fetch details about the file:
```
# print infos
print(reader.get_info_string())

# dict of topics with field names, data-types and message counts
structure = reader.get_structure()

# list of topic names
topics = reader.get_topic_names()

# total number of messages
count = reader.get_total_message_count()

# start and end time in nanoseconds
start_time_ns = reader.time_start_ns
end_time_ns = reader.time_end_ns
```

#### Fetch data from a specific topic:
```
# get a numpy structured array with data from a topic
data = reader.get_data(topic_name)
```

#### Fetch all data:
```
# get a dict of numpy structured arrays with data from all topics
data = reader.get_all_data()
```

#### Fetch a specific amount of data with a start time and number of messages:
```
data = reader.get_data('testtopic', start_time_ns=0, num_messages=1000)
# fetch next block, starting right after the first
data = reader.get_data('testtopic', start_time_ns=data['ts'][-1] + 1, num_messages=1000)
```

#### Example for chunked reader:
```
for chunk in reader.get_data_chunked("testtopic", chunk_size_megabytes=1000):
    print(f'got {chunk.size} messages')
    # --> process data chunk (numpy structured array)!
```

#### Use matplotlib to plot data:
```
import matplotlib.pyplot as plt
for topic_name in reader.get_topic_names():
    data = reader.get_data(topic_name)
    fields = reader.get_structure()[topic_name]['fields']
    dtypes = reader.get_structure()[topic_name]['dtypes']
    channels = []
    for i, field in enumerate(fields):
        if dtypes[i] != 'boolean' and dtypes[i] != 'string' and dtypes[i] != 'array':
            channels.append(field)
    for ch in [ch for ch in channels if ch != 'ts']:
        plt.plot(data['ts'], data[ch], label=ch)

plt.xlabel('Time')
plt.ylabel('Value')
plt.legend()
plt.title('Channels over Time')
plt.show()
```

Please see `reader.py` - there are examples at the end of the file.

## Usage of Data Collector

TODO

## Configure Logging
```
import logging
import databeam_mcap_reader as mr
logging.getLogger('databeam_mcap').setLevel(logging.DEBUG)  # or other logging level
```

## Build wheel files
Wheel files must be specifically built for all supported Python versions.

### Linux / Docker
Make sure Docker is installed and running: https://docs.docker.com/get-docker/
```
make linux_wheels
```
This will run a manylinux Docker container and build the wheel files with the specified Python versions (see Makefile).

### Windows
Make sure Python is installed in all required versions and `py` command is available: https://www.python.org/downloads/windows/

Install Visual Studio 2022 with Python and C++ extensions: https://visualstudio.microsoft.com/downloads/

Install Conan natively: https://conan.io/downloads
```
conan
conan profile detect --force
```

Open terminal and run:
```
.\build_wheels_windows.ps1 <python_version> [<python_version> ...]
Example:
 .\build_wheels_windows.ps1 3.10 3.11 3.12 3.13
```


## Development / Testing (Linux)

### Build only c++ extension for development
```
make dev

python3
import build_dev._core as mr
mr.parse_mcap(...)
```

### Test built wheel
```
make wheel

python3 -m venv venv_test
. ./venv_test/bin/activate
pip install dist/databeam_mcap_readerXXX.whl

python3 -c "import databeam_mcap_reader as mr; import numpy as np; reader = mr.McapReader(); mr.parse_mcap('whee', 't', np.dtype([]), 1)"
```
OK, if there are no import-errors and it complains, that `whee` file is missing.


## License
Distributed under the MIT license. See `LICENSE.txt` file for more information.


## Contact
Virtual Vehicle Research GmbH: [https://www.v2c2.at](https://www.v2c2.at)

Project Lead: Peter Sammer - peter.sammer@v2c2.at

This repository contains only public open-source components: [https://github.com/virtual-vehicle/databeam](https://github.com/virtual-vehicle/databeam)

We gladly offer support, custom installations and extensions for devices, test-benches, experiments and more.


## Acknowledgments

Virtual Vehicle Research GmbH has received funding within COMET Competence Centers for Excellent Technologies from the Austrian Federal Ministry for Climate Action, the Austrian Federal Ministry for Labour and Economy, the Province of Styria (Dept. 12) and the Styrian Business Promotion Agency (SFG). The Austrian Research Promotion Agency (FFG) has been authorised for the programme management.
