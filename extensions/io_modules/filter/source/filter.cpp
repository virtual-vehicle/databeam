#include "filter.h"
#include <iostream>
#include "ModuleInterface.h"
#include "Logger.h"
#include "Utils.h"
#include "JsonWriter.h"
#include "ConfigFactory.h"
#include <unistd.h>

#include "AverageFilter.hpp"
#include "ExponentialAverageFilter.hpp"
#include "MedianFilter.hpp"

FilterModule::FilterModule(EnvConfig* env_config)
{
    //store environment config
    this->env_config = env_config;

    ConfigFactory cfg;
    cfg.string("input_module", "module/topic");
    cfg.string_array("channels", {"channel"}).resizeable();
    cfg.string("timebase", "samples").select({"samples", "time"});
    cfg.number("timebase_value", 10.0);
    cfg.string("method", "average").select({"average", "exponential_average", "median"});

    default_config = cfg.get_json_str();

    //parse default config
    config_json.parse(default_config);

    //init sensor name and type
    this->setName(env_config->get("MODULE_NAME"));
    this->setType("filter");

    this->filter = nullptr;
}

FilterModule::~FilterModule()
{
    this->logger->debug("FilterModule Shutdown.");
}

void FilterModule::init(ModuleInterface* data_interface, Logger* logger, DataBroker* data_broker)
{
    //store data interface and logger references
    this->data_interface = data_interface;
    this->logger = logger;
    this->data_broker = data_broker;

    // TODO
}

std::string FilterModule::getConfig()
{
    return config_json.stringify();
}

std::string FilterModule::getDefaultConfig()
{
    return default_config;
}

std::string FilterModule::validateConfig(Json& json)
{
    // TODO

    return "";
}

void FilterModule::applyConfig(Json& json)
{
    this->filter_lock.lock();

    this->unsubscribeChannels(this->subscribed_topic);

    // store config
    std::string json_str = json.stringify();
    config_json.parse(json_str);

    // log current config
    logger->debug("Config: ");

    if(this->filter != nullptr)
    {
        delete this->filter;
        this->filter = nullptr;
    }

    this->subscribed_topic = this->env_config->get("DB_ID") + "/m/" + config_json.getString("input_module");
    std::string filter_type = config_json.getString("method");
    if(filter_type == "average")
    {
        logger->info("Set new moving average filter.");
        this->filter = new AverageFilter();
    }
    else if(filter_type == "exponential_average")
    {
        logger->info("Set new exponential moving average filter.");
        this->filter = new ExponentialAverageFilter();
    }
    else if(filter_type == "median")
    {
        logger->info("Set new moving median filter.");
        this->filter = new MedianFilter();
    }
    else
    {
        logger->error("Invalid filter method <" + filter_type + "> provided.");
    }

    if(this->filter == nullptr)
    {
        this->filter_lock.unlock();
        return;
    }

    this->filter->setChannelNames(this->config_json.getStringArray("channels"));
    this->filter->configureBase(this->config_json);
    this->filter->configure(this->config_json);

    this->subscribeChannels(this->subscribed_topic);

    this->filter_lock.unlock();
}

bool FilterModule::prepareStartSampling()
{
    return true;
}

void FilterModule::subscribeChannels(std::string topic)
{
    if(this->filter == nullptr)
        return;

    this->logger->info("Subscribing to module topic " + topic);
    data_interface->getConnectionManager()->subscribe(topic, this);
}

void FilterModule::unsubscribeChannels(std::string topic)
{
    if(topic == "")
        return;

    this->logger->info("Unsubscribing from module topic " + topic);
    data_interface->getConnectionManager()->unsubscribe(topic, this);
}

bool FilterModule::startSampling()
{
    filter->clearData();
    return true;
}

bool FilterModule::prepareStopSampling()
{
    return true;
}

bool FilterModule::stopSampling()
{
    return true;
}

std::vector<McapSchema> FilterModule::getMcapSchemas()
{
    std::vector<std::string> channels_list = this->config_json.getStringArray("channels");

    std::vector<McapSchema> schema_list;
    McapSchema module_schema;
    module_schema.setTopic(getName());

    for(size_t i = 0; i < channels_list.size(); i++)
    {
        std::string channel_name = channels_list[i];
        module_schema.addProperty(channel_name + "_filtered", "number");
    }

    schema_list.push_back(module_schema);
    return schema_list;
}

void FilterModule::notify_subscriber(std::string key, std::string payload)
{
    TimeSource time_source;
    long long curr_time = time_source.now();

    // This only happens when we configure new filters, which restarts the filter process.
    // We do not need any previous data anymore and can just return instead of wait.
    bool lock_free = this->filter_lock.try_lock();
    if(!lock_free)
        return;

    if(this->subscribed_topic != key)
    {
        this->filter_lock.unlock();
        return;
    }
    if(this->filter == nullptr)
    {
        this->filter_lock.unlock();
        return;
    }

    Json payload_json(payload);
    JsonWriter json_writer;
    json_writer.begin();
    long long payload_ts = payload_json.getInt64("ts");

    for(const std::string& channel : *(this->filter->getChannelNames()))
    {
        if(!payload_json.has(channel))
            continue;
        this->filter->updateData(payload_ts, payload_json.getDouble(channel), channel);

        if(!this->data_broker->getSamplingRunning())
            continue;

        double filtered_value = this->filter->compute(channel);
        json_writer.write(std::string(channel + "_filtered"), filtered_value);
    }

    data_broker->lock(); 
    data_broker->data_in((uint64_t) payload_ts, json_writer);
    data_broker->unlock();

    this->filter_lock.unlock();
}
