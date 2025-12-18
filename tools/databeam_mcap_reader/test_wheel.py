import databeam_mcap_reader as mr

import logging
logging.basicConfig(format='%(asctime)s %(levelname)-7s | %(message)s', level=logging.DEBUG)
logging.getLogger('databeam_mcap').setLevel(logging.DEBUG)

reader = mr.McapReader()
reader.open('testdata_multi_measurement/dummy_small_json.mcap')
# print infos
print(reader.get_info_string())

# dict of topics with field names, data-types and message counts
structure = reader.get_structure()

# list of topic names
topics = reader.get_topic_names()

# total number of messages
count = reader.get_total_message_count()
# get a numpy structured array with data from a topic
data = reader.get_data(topics[0])

# get a dict of numpy structured arrays with data from all topics
data = reader.get_all_data()
print(data)

data = reader.get_data(topics[0], start_time_ns=0, num_messages=1000)
# fetch next block, starting right after the first
data = reader.get_data(topics[0], start_time_ns=data['ts'][-1] + 1, num_messages=1000)

for chunk in reader.get_data_chunked(topics[0], chunk_size_megabytes=1000):
    print(f'got {chunk.size} messages')
    # --> process data chunk (numpy structured array)!

reader.close()
print('\n\ntest-script finished')
