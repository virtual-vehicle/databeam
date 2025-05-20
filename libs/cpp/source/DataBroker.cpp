
#define MCAP_IMPLEMENTATION
#include "DataBroker.h"
#include "JsonWriter.h"
#include "TimeSource.h"
#include "Utils.h"

void* all_thread(void* data_broker_ptr) 
{
    DataBroker* data_broker = (DataBroker*) data_broker_ptr;
    AsyncQueue<LiveDataBlock>* all_queue = data_broker->getAllQueue();
    Logger* logger = data_broker->getLogger();
    ConnectionManager* cm = data_broker->getConnectionManager();
    std::string topic = data_broker->getAllTopic();
    std::vector<std::string> schema_all_topics = data_broker->GetSchemaAllTopics();

    //log thread start
    logger->debug("[Live-Data] 'All' Thread Started");

    while(true)
    {
        //get next sample from queue
        LiveDataBlock sample = all_queue->pop();

        //kill thread
        if(sample.schema_index < 0) break;

        //log sample
        //logger->debug("Publish All");

        if(sample.schema_index < (int)schema_all_topics.size())
        {
            cm->publish(schema_all_topics[sample.schema_index], sample.json_data_string);
        }

        //publish sample
        /*if(sample.schema_index == 0) 
        {
            cm->publish(topic, sample.json_data_string);
        }*/
    }

    //log thread shutdown
    logger->debug("[Live-Data] 'All' Thread Shutdown");

    //exit thread
    pthread_exit(NULL);
}

void* fixed_thread(void* data_broker_ptr) 
{
    DataBroker* data_broker = (DataBroker*) data_broker_ptr;
    AsyncQueue<LiveDataBlock>* fixed_queue = data_broker->getFixedQueue();
    Logger* logger = data_broker->getLogger();
    ConnectionManager* cm = data_broker->getConnectionManager();
    std::string fixed_topic = data_broker->getFixedTopic();
    std::vector<std::string> schema_fixed_topics = data_broker->GetSchemaFixedTopics();

    //log thread start
    logger->debug("[Live-Data] 'Fixed' Thread Started");

    while(true)
    {
        //get next sample from queue
        LiveDataBlock sample = fixed_queue->pop();

        //kill thread
        if(sample.schema_index < 0) break;

        //log sample
        //logger->debug("Publish Fixed");

        if(sample.schema_index < (int)schema_fixed_topics.size())
        {
            cm->publish(schema_fixed_topics[sample.schema_index], sample.json_data_string);
        }

        /*if(sample.schema_index == 0)
        {
            //publish sample
            cm->publish(fixed_topic, sample.json_data_string);
        }*/
    }

    //log thread shutdown
    logger->debug("[Live-Data] 'Fixed' Thread Shutdown");

    //exit thread
    pthread_exit(NULL);
}

DataBroker::DataBroker()
{
    //allocate mcap writer
    mcap_writer = new mcap::McapWriter();
    kill_live_data_block.schema_index = -1;
    kill_live_data_block.json_data_string = "";
}

DataBroker::~DataBroker()
{
    //deallocate mcap writer
    if(mcap_writer != nullptr) delete mcap_writer;
}

void DataBroker::start_threads()
{
    //create parse thread
    int all_return_value = pthread_create(&all_thread_id, NULL, all_thread, (void *)this);
    int fixed_return_value = pthread_create(&fixed_thread_id, NULL, fixed_thread, (void *)this);

    //log error if thread could not be created
    if(all_return_value != 0) logger->error("[Live-Data] 'All' thread created with error: " + std::to_string(all_return_value));
    if(fixed_return_value != 0) logger->error("[Live-Data] 'Fixed' thread created with error: " + std::to_string(fixed_return_value));
}

void DataBroker::stop_threads()
{
    //empty string kills thread
    all_queue.push(kill_live_data_block);
    fixed_queue.push(kill_live_data_block);

    //join with threads
    void* all_return_value;
    void* fixed_return_value;
    int all_join_return_value = pthread_join(all_thread_id, &all_return_value);
    int fixed_join_return_value = pthread_join(fixed_thread_id, &fixed_return_value);

    //check return values
    if(all_join_return_value != 0) logger->error("[Live-Data] 'All' thread joined with error.");
    if(fixed_join_return_value != 0) logger->error("[Live-Data] 'Fixed' thread joined with error.");
}

void DataBroker::shutdown()
{
    logger->debug("DataBroker shutdown.");

    stop_threads();

    logger->debug("DataBroker Threads joined.");

    //delete mcap writer
    if(mcap_writer != nullptr) delete mcap_writer;
    mcap_writer = nullptr;
}

void DataBroker::init(ConnectionManager* connection_manager, DataConfig* data_config, Logger* logger, 
    std::string db_id, std::string module_name)
{
    //store parameters
    this->connection_manager = connection_manager;
    this->data_config = data_config;
    this->db_id = db_id;
    this->module_name = module_name;
    this->logger = logger;

    //init all and fixed topics
    this->all_topic = db_id + "/m/" + module_name + "/liveall";
    this->fixed_topic = db_id + "/m/" + module_name + "/livedec";

    //start all and fixed threads
    start_threads();
}

AsyncQueue<LiveDataBlock>* DataBroker::getAllQueue()
{
    return &all_queue;
}

AsyncQueue<LiveDataBlock>* DataBroker::getFixedQueue()
{
    return &fixed_queue;
}

Logger* DataBroker::getLogger()
{
    return logger;
}

ConnectionManager* DataBroker::getConnectionManager()
{
    return connection_manager;
}

std::string DataBroker::getAllTopic()
{
    return all_topic;
}

std::string DataBroker::getFixedTopic()
{
    return fixed_topic;
}

std::vector<std::string> DataBroker::GetSchemaAllTopics()
{
    return this->schema_all_topics;
}

std::vector<std::string> DataBroker::GetSchemaFixedTopics()
{
    return this->schema_fixed_topics;
}

void DataBroker::lock()
{
    this->broker_lock.lock();
}

void DataBroker::unlock()
{
    this->broker_lock.unlock();
}

void DataBroker::prepareCapture(std::string module_name, std::string module_type,
                                std::string file_path, std::vector<McapSchema>& schema_list)
{
    if(capture_running)
    {
        logger->warning("[DataBroker] Capture running on prepareCapture.");
        return;
    }

    if(mcap_open)
    {
        logger->warning("[DataBroker] MCAP file already open on prepareCapture.");
        return;
    }

    //only prepare mcap file if capturing is enabled
    if(!data_config->getEnableCapturing()) return;

    //log start
    logger->debug("[DataBroker] start measurement, prepare MCAP write.");

    //re-create mcap writer
    mcap_writer->~McapWriter();
    mcap_writer = new ((unsigned char*)mcap_writer) mcap::McapWriter();

    //open mcap file for writing
    auto options = mcap::McapWriterOptions("");
    const auto res = mcap_writer->open(file_path, options);

    //clear channel ids
    channel_ids.clear();

    //add schemas
    for(unsigned int i = 0; i < schema_list.size(); i++)
    {
        std::string dtype_name = schema_list[i].get_dtype_name();
        // Set dtype name to module name if no specific dype name was provided
        if(schema_list[i].get_dtype_name() == "")
            dtype_name = module_type + "_" + std::to_string(i);
        std::string topic_name = schema_list[i].get_topic();
        if(schema_list[i].get_topic() == "")
            topic_name = module_name;

        logger->debug(schema_list[i].get_schema_string());

        //create schema
        mcap::Schema schema(dtype_name, "jsonschema", schema_list[i].get_schema_string());
        mcap_writer->addSchema(schema);

        //create and add channel
        mcap::Channel channel(topic_name, "json", schema.id);
        mcap_writer->addChannel(channel);
        channel_ids.push_back(channel.id);
    }

    //make sure mcap file is open 
    if (!res.ok())
    {
        logger->debug("Could not open file: " + file_path);
        return;
    }

    //mcap file is open for writing
    mcap_open = true;
}

void DataBroker::startCapture()
{
    if(capture_running)
    {
        logger->warning("[DataBroker] Capture running on startCapture.");
        return;
    }

    if(!mcap_open && data_config->getEnableCapturing())
    {
        logger->warning("[DataBroker] MCAP file not open on startCapture with enabled capturing.");
        return;
    }

    lock();
    capture_running = true;
    frame_index = 0; 
    unlock();
}

void DataBroker::stopCapture()
{
    if(!capture_running)
    {
        logger->warning("[DataBroker] Capture not running on stop.");
        return;
    }

    lock();
    if(mcap_writer != nullptr && mcap_open) mcap_writer->close();
    mcap_open = false;
    capture_running = false;
    unlock();
}

bool DataBroker::getCaptureRunning()
{
    return capture_running;
}

bool DataBroker::startSampling()
{
    if(sampling_running)
    {
        logger->warning("[DataBroker] Sampling already running.");
        return false;
    }

    lock();
    current_ts = 0;
    current_ts_list.clear();
    for(unsigned int i = 0; i < schema_all_topics.size(); i++) current_ts_list.push_back(0);
    this->sampling_running = true;
    unlock();

    return true;
}

bool DataBroker::stopSampling()
{
    if(!sampling_running)
    {
        logger->warning("[DataBroker] Sampling not running.");
        return false;
    }

    this->sampling_running = false;

    return true;
}

bool DataBroker::getSamplingRunning()
{
    return this->sampling_running;
}

void DataBroker::setSchemas(std::vector<McapSchema>& schema_list)
{
    stop_threads();

    //clear all schema topics
    schema_all_topics.clear();
    schema_fixed_topics.clear();

    //create new list of topics for each schema
    for(unsigned int i = 0; i < schema_list.size(); i++)
    {
        std::string topic = schema_list[i].get_topic();
        schema_all_topics.push_back(this->db_id + "/m/" + this->module_name + "/" + topic + "/liveall") ;
        schema_fixed_topics.push_back(db_id + "/m/" + module_name + "/" + topic + "/livedec");
    }

    logger->debug("Schema All Topics: " + Utils::vectorToString(schema_all_topics));
    logger->debug("Schema Fixed Topics: " + Utils::vectorToString(schema_fixed_topics));

    start_threads();
}

void DataBroker::data_in(long long timestamp, JsonWriter &json_writer, unsigned int schema_index, bool mcap, bool live, bool latest)
{
    if(!sampling_running)
        return;

    //points to either latest or live json writer if live flag is set
    JsonWriter* temp_live_writer = nullptr;

    //copy json writer to latest or live writer
    if(latest)
    {
        latest_json_writer.init(json_writer);
        latest_json_writer.write("ts", timestamp);
        latest_json_writer.end();

        if(live) temp_live_writer = &latest_json_writer;
    }
    else
    {
        if(live)
        {
            live_json_writer.init(json_writer);
            live_json_writer.write("ts", timestamp);
            live_json_writer.end();
            temp_live_writer = &live_json_writer;
        }
    }
    
    //write to mcap file if capture is running and mcap flag is set
    if(capture_running && mcap && mcap_open)
    {
        if(schema_index >= channel_ids.size())
        {
            logger->error("Schema index out of bounds.");
            return;
        }

        //finish mcap writer
        json_writer.end();

        //create mcap message
        mcap::Message msg;
        msg.channelId = channel_ids[schema_index];
        msg.logTime = timestamp;
        msg.publishTime = timestamp;
        msg.sequence = frame_index++;
        msg.data = reinterpret_cast<const std::byte *>(json_writer.getStringPtr()->data());
        msg.dataSize = json_writer.getStringPtr()->size();

        //write message to mcap file
        auto res = mcap_writer->write(msg);

        //make sure there was no error
        if(!res.ok()) logger->error("MCAP write error: " + res.message);
    }

    //write live data if live flag is set
    if(live)
    {
        //forward all samples if enabled
        if(data_config->getAllEnabled())
        {
            LiveDataBlock data_block = {(int)schema_index, *temp_live_writer->getStringPtr()};
            all_queue.push(data_block);
        }

        //forward fixed samples if enabled
        if(data_config->getFixedEnabled())
        {
            if(current_ts_list[schema_index] == 0)
            {
                current_ts_list[schema_index] = timestamp;
                LiveDataBlock data_block = {(int)schema_index, *temp_live_writer->getStringPtr()};
                fixed_queue.push(data_block);
            }
            else
            {
                double delta_ts = (double)(timestamp - current_ts_list[schema_index]) * 0.000000001;
                
                if(delta_ts >= data_config->getFixedDeltaTime())
                {
                    current_ts_list[schema_index] = timestamp;
                    LiveDataBlock data_block = {(int)schema_index, *temp_live_writer->getStringPtr()};
                    fixed_queue.push(data_block);
                }
            }
        }
        else
        {
            current_ts_list[schema_index] = 0;
        }
    }
}

std::string DataBroker::getLatestData()
{
    //sample string to return
    std::string to_return;

    //acquire data broker lock
    lock();

    //get current json sample string or empty json
    if(latest_json_writer.getStringPtr()->size() > 0)
    {
        to_return = *latest_json_writer.getStringPtr();
    }
    else
    {
        to_return = "{}";
    }
    
    //release data broker lock
    unlock();

    //return sample json string
    return to_return;
}