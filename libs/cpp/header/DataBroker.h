#pragma once
#include <string>
#include <vector>
#include <mutex>
#include <pthread.h>
#include "AsyncQueue.h"
#include <mcap/writer.hpp>
#include "Logger.h"
#include "JsonWriter.h"
#include "McapSchema.h"
#include "DataConfig.h"
#include "ConnectionManager.h"

struct LiveDataBlock
{
    int schema_index;
    std::string json_data_string;
};

class DataBroker
{
public:
    DataBroker();
    ~DataBroker();

    void init(ConnectionManager* connection_manager, DataConfig* data_config, Logger* logger, 
        std::string db_id, std::string module_name);
    void prepareCapture(std::string module_name, std::string module_type,
                        std::string file_path, std::vector<McapSchema>& schema_list);
    void startCapture();
    void stopCapture();
    void data_in(long long timestamp, JsonWriter &json_writer, unsigned int schema_index = 0, bool mcap = true, bool live = true, bool latest = true);
    void lock();
    void unlock();
    void shutdown();
    bool getCaptureRunning();
    bool startSampling();
    bool stopSampling();
    bool getSamplingRunning();
    void setSchemas(std::vector<McapSchema>& schema_list);

    std::string getLatestData();
    AsyncQueue<LiveDataBlock>* getAllQueue();
    AsyncQueue<LiveDataBlock>* getFixedQueue();
    Logger* getLogger();
    ConnectionManager* getConnectionManager();
    std::string getAllTopic();
    std::string getFixedTopic();
    std::vector<std::string> GetSchemaAllTopics();
    std::vector<std::string> GetSchemaFixedTopics();
private:
    void start_threads();
    void stop_threads();

    ConnectionManager* connection_manager = nullptr;
    DataConfig* data_config;
    std::string db_id = "default";
    std::string module_name = "default";
    Logger* logger = nullptr;
    std::string all_topic = "";  // e.g. "db_debug/m/module_name/liveall"
    std::string fixed_topic = "";  // e.g. "db_debug/m/module_name/livedec"
    std::vector<std::string> schema_all_topics;
    std::vector<std::string> schema_fixed_topics;
    mcap::McapWriter* mcap_writer = nullptr;
    std::vector<mcap::ChannelId> channel_ids;
    uint32_t frame_index = 0;
    std::mutex broker_lock;
    JsonWriter latest_json_writer;
    JsonWriter live_json_writer;
    bool mcap_open = false;
    bool capture_running = false;
    bool sampling_running = false;

    //live data thread ids and queues
    pthread_t all_thread_id;
    pthread_t fixed_thread_id;
    AsyncQueue<LiveDataBlock> all_queue;
    AsyncQueue<LiveDataBlock> fixed_queue;
    LiveDataBlock kill_live_data_block;

    //current time stamp for fixed live data
    long long current_ts = 0;
    std::vector<long long> current_ts_list;
};