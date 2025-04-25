#include "template_module.h"
#include <iostream>
#include "ModuleInterface.h"
#include "Logger.h"
#include "Utils.h"
#include "JsonWriter.h"
#include "ConfigFactory.h"
#include <unistd.h>

void* worker_thread(void* io_module_ptr) 
{
    // cast parameter to io-module type
    TemplateModule* io_module = (TemplateModule*) io_module_ptr;

    // create time source for timestamps
    TimeSource time_source;

    // get the logger
    Logger* logger = io_module->getLogger();
    logger->debug("Worker thread started.");

    // create json writer
    JsonWriter json_writer;

    // get data broker
    DataBroker* data_broker = io_module->getDataBroker();

    while(!io_module->getThreadKillFlag())
    {
        // lock data broker
        data_broker->lock();  

        // begin a new row
        json_writer.begin();
        
        // record the sample
        json_writer.write(std::string("CH_X"), (double)1.23);

        // data broker calls json_writer.end()
        data_broker->data_in((uint64_t) time_source.now(), json_writer);

        logger->debug("got: \n" + json_writer.getString());

        // unlock data broker
        data_broker->unlock();
        // sleep for 1 second
        sleep(1);
    }

    // log thread shutdown
    logger->debug("Worker thread shutdown.");

    // exit thread
    pthread_exit(NULL);
}

TemplateModule::TemplateModule(EnvConfig* env_config)
{
    //store environment config
    this->env_config = env_config;

    //generate config with default values via the config factory
    ConfigFactory cfg;
    cfg.string("some_value", "dummy");
    default_config = cfg.get_json_str();

    //parse default config
    config_json.parse(default_config);

    //init sensor name and type
    this->setName(env_config->get("MODULE_NAME"));
    this->setType("template_module");
}

TemplateModule::~TemplateModule()
{
    this->logger->debug("TemplateModule Shutdown.");
}

void TemplateModule::init(ModuleInterface* data_interface, Logger* logger, DataBroker* data_broker)
{
    //store data interface and logger references
    this->data_interface = data_interface;
    this->logger = logger;
    this->data_broker = data_broker;

    // TODO
}

std::string TemplateModule::getConfig()
{
    return config_json.stringify();
}

std::string TemplateModule::getDefaultConfig()
{
    return default_config;
}

std::string TemplateModule::validateConfig(Json& json)
{
    // TODO

    return "";
}

void TemplateModule::applyConfig(Json& json)
{
    // store config
    std::string json_str = json.stringify();
    config_json.parse(json_str);

    // log current config
    logger->debug("Config: ");

    // TODO
}

bool TemplateModule::prepareStartSampling()
{
    // create parse thread
    worker_thread_kill = false;
    int return_value = pthread_create(&worker_thread_id, NULL, worker_thread, (void *)this);
    // log error if thread could not be created
    if(return_value != 0) logger->error("Start worker thread error: " + std::to_string(return_value));

    // TODO

    return true;
}

bool TemplateModule::startSampling()
{
    // TODO

    return true;
}

bool TemplateModule::prepareStopSampling()
{
    // join with thread
    worker_thread_kill = true;
    void* return_value;
    pthread_join(worker_thread_id, &return_value);

    // TODO

    return true;
}

bool TemplateModule::stopSampling()
{
    // TODO

    return true;
}

std::vector<McapSchema> TemplateModule::getMcapSchemas()
{
    //create module schema list for mcap capture and live data forwarding
    McapSchema module_schema;
    module_schema.setTopic("template_schema");
    module_schema.addProperty("CH_X", "number");
    return std::vector<McapSchema>{module_schema};
}