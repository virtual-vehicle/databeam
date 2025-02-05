
#define MCAP_IMPLEMENTATION
#include "DataBroker.h"
#include "JsonWriter.h"
#include "TimeSource.h"

void* all_thread(void* data_broker_ptr) 
{
    DataBroker* data_broker = (DataBroker*) data_broker_ptr;
    AsyncQueue<std::string>* all_queue = data_broker->getAllQueue();
    Logger* logger = data_broker->getLogger();
    ConnectionManager* cm = data_broker->getConnectionManager();
    std::string topic = data_broker->getAllTopic();

    //log thread start
    logger->debug("[Live-Data] 'All' Thread Started");

    while(true)
    {
        //get next sample from queue
        std::string sample = all_queue->pop();

        //kill thread
        if(sample == "") break;

        //log sample
        //logger->debug("Publish All");

        //publish sample
        cm->publish(topic, sample);
    }

    //log thread shutdown
    logger->debug("[Live-Data] 'All' Thread Shutdown");

    //exit thread
    pthread_exit(NULL);
}

void* fixed_thread(void* data_broker_ptr) 
{
    DataBroker* data_broker = (DataBroker*) data_broker_ptr;
    AsyncQueue<std::string>* fixed_queue = data_broker->getFixedQueue();
    Logger* logger = data_broker->getLogger();
    ConnectionManager* cm = data_broker->getConnectionManager();
    std::string fixed_topic = data_broker->getFixedTopic();

    //log thread start
    logger->debug("[Live-Data] 'Fixed' Thread Started");

    while(true)
    {
        //get next sample from queue
        std::string sample = fixed_queue->pop();

        //kill thread
        if(sample == "") break;

        //log sample
        //logger->debug("Publish Fixed");

        //publish sample
        cm->publish(fixed_topic, sample);
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
}

DataBroker::~DataBroker()
{
    //deallocate mcap writer
    if(mcap_writer != nullptr) delete mcap_writer;
}

void DataBroker::shutdown()
{
    logger->debug("DataBroker shutdown.");

    //empty string kills thread
    all_queue.push("");
    fixed_queue.push("");

    //join with threads
    void* all_return_value;
    void* fixed_return_value;
    int all_join_return_value = pthread_join(all_thread_id, &all_return_value);
    int fixed_join_return_value = pthread_join(fixed_thread_id, &fixed_return_value);

    //check return values
    if(all_join_return_value != 0) logger->error("[Live-Data] 'All' thread joined with error.");
    if(fixed_join_return_value != 0) logger->error("[Live-Data] 'Fixed' thread joined with error.");

    if(mcap_writer != nullptr) delete mcap_writer;
    mcap_writer = nullptr;
}

void DataBroker::init(ConnectionManager* connection_manager, DataConfig* data_config, 
    Logger* logger, std::string all_topic, std::string fixed_topic)
{
    //store parameters
    this->connection_manager = connection_manager;
    this->data_config = data_config;
    this->logger = logger;
    this->all_topic = all_topic;
    this->fixed_topic = fixed_topic;

    //create parse thread
    int all_return_value = pthread_create(&all_thread_id, NULL, all_thread, (void *)this);
    int fixed_return_value = pthread_create(&fixed_thread_id, NULL, fixed_thread, (void *)this);

    //log error if thread could not be created
    if(all_return_value != 0) logger->error("[Live-Data] 'All' thread created with error: " + std::to_string(all_return_value));
    if(fixed_return_value != 0) logger->error("[Live-Data] 'Fixed' thread created with error: " + std::to_string(fixed_return_value));
}

AsyncQueue<std::string>* DataBroker::getAllQueue()
{
    return &all_queue;
}

AsyncQueue<std::string>* DataBroker::getFixedQueue()
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

    if(!mcap_open)
    {
        logger->warning("[DataBroker] MCAP file not open on startCapture.");
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
    if(mcap_writer != nullptr) mcap_writer->close();
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

void DataBroker::data_in(long long timestamp, JsonWriter &json_writer, unsigned int schema_index, bool mcap, bool live, bool latest)
{
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
    if(capture_running && mcap)
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
            all_queue.push(*temp_live_writer->getStringPtr());
        }

        //forward fixed samples if enabled
        if(data_config->getFixedEnabled())
        {
            if(current_ts == 0)
            {
                current_ts = timestamp;
                fixed_queue.push(*temp_live_writer->getStringPtr());
            }
            else
            {
                double delta_ts = (double)(timestamp - current_ts) * 0.000000001;
                
                if(delta_ts >= data_config->getFixedDeltaTime())
                {
                    current_ts = timestamp;
                    fixed_queue.push(*temp_live_writer->getStringPtr());
                }
            }
        }
        else
        {
            current_ts = 0;
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