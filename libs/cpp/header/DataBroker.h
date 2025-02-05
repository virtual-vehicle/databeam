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

class DataBroker
{
public:
    DataBroker();
    ~DataBroker();

    void init(ConnectionManager* connection_manager, DataConfig* data_config, Logger* logger, 
        std::string all_topic, std::string fixed_topic);
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

    std::string getLatestData();
    AsyncQueue<std::string>* getAllQueue();
    AsyncQueue<std::string>* getFixedQueue();
    Logger* getLogger();
    ConnectionManager* getConnectionManager();
    std::string getAllTopic();
    std::string getFixedTopic();
private:
    ConnectionManager* connection_manager = nullptr;
    DataConfig* data_config;
    Logger* logger = nullptr;
    std::string all_topic = "";  // e.g. "db_debug/m/module_name/liveall"
    std::string fixed_topic = "";  // e.g. "db_debug/m/module_name/livedec"
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
    AsyncQueue<std::string> all_queue;
    AsyncQueue<std::string> fixed_queue;

    //current time stamp for fixed live data
    long long current_ts = 0;
};