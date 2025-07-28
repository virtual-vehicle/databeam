#include "IOModule.h"
#include "JsonWriter.h"
#include "Utils.h"

IOModule::IOModule()
{

}

IOModule::~IOModule()
{

}

void IOModule::init(ModuleInterface* data_interface, Logger* logger, DataBroker* data_broker)
{
    this->data_interface = data_interface;
    this->logger = logger;
    this->data_broker = data_broker;
}

void IOModule::setName(std::string module_name)
{
    this->module_name = module_name;
}

void IOModule::setType(std::string module_type)
{
    this->module_type = module_type;
}

std::string IOModule::getMeasurementName()
{
    return measurement_name;
}

std::string IOModule::getName()
{
    return module_name;
}

std::string IOModule::getType()
{
    return module_type;
}

bool IOModule::prepareStartCapture()
{
    return true;
}

bool IOModule::startCapture()
{
    return true;
}

bool IOModule::prepareStopCapture()
{
    return true;
}

bool IOModule::stopCapture()
{
    return true;
}

bool IOModule::prepareStartSampling()
{
    return true;
}

bool IOModule::startSampling()
{
    return true;
}

bool IOModule::prepareStopSampling()
{
    return true;
}

bool IOModule::stopSampling()
{
    return true;
}


std::string IOModule::setConfig(Json& json)
{
    //validate config
    std::string validation_error_str = this->validateConfig(json);

    //return error string if validation failed
    if(validation_error_str != "") 
    {
        logger->debug("Config invalid: " + validation_error_str);
        return validation_error_str;
    }

    //apply the config
    this->applyConfig(json);
    return "";
}

std::string IOModule::validateConfig(Json& json)
{
    return "";
}

void IOModule::applyConfig(Json& json)
{
    return;
}

std::string IOModule::getConfig()
{
    return "";
}

std::string IOModule::getDefaultConfig()
{
    return "";
}

std::string IOModule::getMetaDataTemplate()
{
    JsonWriter json_writer;
    json_writer.begin();

    // get module metadata
    getMetaData(json_writer);

    // get mcap schema list
    std::vector<McapSchema> mcap_schemans = getMcapSchemas();

    // holds list of topics
    std::vector<std::string> topics;

    // get list of mcap topic strings from schemas
    for(unsigned int i = 0; i < mcap_schemans.size(); i++)
    {
        topics.push_back(mcap_schemans[i].get_topic());
    }

    // write topics list to meta json
    json_writer.write("_mcap_topics", topics);

    // write module config to metadata
    json_writer.write("config", Utils::replaceCharWithString(getConfig(), '\"', "\\\""));

    // finish json writer and return json string
    json_writer.end();
    return json_writer.getString();
}

void IOModule::getMetaData(JsonWriter& json_writer)
{
    return;
}

std::vector<McapSchema> IOModule::getMcapSchemas()
{
    //create default schema
    JsonWriter json_writer;
    json_writer.begin();
    json_writer.write("type", "object");
    json_writer.beginObject("properties");
    json_writer.endObject();
    json_writer.end(); 

    //create schema list
    std::vector<McapSchema> schema_list;

    //add schema to list
    McapSchema default_schema;
    default_schema.setTopic(getName());
    schema_list.push_back(default_schema);

    //return schema list
    return schema_list;
}

void IOModule::configEvent(std::string cfg_key)
{
    return;
}

Logger* IOModule::getLogger()
{
    return this->logger;
}

DataBroker* IOModule::getDataBroker()
{
    return this->data_broker;
}

ModuleInterface* IOModule::getDataInterface()
{
    return this->data_interface;
}
