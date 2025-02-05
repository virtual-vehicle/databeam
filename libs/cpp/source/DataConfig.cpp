#include "DataConfig.h"
#include "Utils.h"
#include "Json.h"
#include "JsonWriter.h"
#include "NetworkMessages.h"

DataConfig::DataConfig()
{
    
}

DataConfig::~DataConfig()
{

}

void DataConfig::init(std::string module_data_config_file)
{
    this->module_data_config_file = module_data_config_file;
    readFromFile();
}

bool DataConfig::getAllEnabled()
{
    return enable_live_all_samples;
}

bool DataConfig::getFixedEnabled()
{
    return enable_live_fixed_rate;
}

double DataConfig::getFixedDeltaTime()
{
    return fixed_delta_time;
}

void DataConfig::store(ModuleDataConfigQuery* data_config_query)
{
    enable_capturing = data_config_query->module_data_config.enable_capturing;
    enable_live_all_samples = data_config_query->module_data_config.enable_live_all_samples;
    enable_live_fixed_rate = data_config_query->module_data_config.enable_live_fixed_rate;
    live_rate_hz = data_config_query->module_data_config.live_rate_hz;
    if(live_rate_hz > 0.0001f) fixed_delta_time = 1.0f / live_rate_hz;
    storeToFile();
}

void DataConfig::getReply(ModuleDataConfig* module_data_config)
{
    module_data_config->enable_capturing = enable_capturing;
    module_data_config->enable_live_all_samples = enable_live_all_samples;
    module_data_config->enable_live_fixed_rate = enable_live_fixed_rate;
    module_data_config->live_rate_hz = live_rate_hz;
}

void DataConfig::storeToFile()
{
    //make sure config path has been set
    if(module_data_config_file == "") return;
    
    //create json
    JsonWriter json_writer;
    json_writer.begin();
    json_writer.write("enable_capturing", enable_capturing);
    json_writer.write("enable_live_all_samples", enable_live_all_samples);
    json_writer.write("enable_live_fixed_rate", enable_live_fixed_rate);
    json_writer.write("live_rate_hz", live_rate_hz);
    json_writer.end();

    //write json to data config file
    Utils::write_string_to_file(module_data_config_file, json_writer.getString());
}

void DataConfig::readFromFile()
{
    //make sure config path has been set
    if(module_data_config_file == "") return;

    //try to read data config json from file
    std::string data_config_json_str;
    Utils::read_file_to_string(module_data_config_file, data_config_json_str);

    //leave if file does not exist
    if(data_config_json_str == "") return;

    //read data config from json
    Json json;
    json.parse(data_config_json_str);
    enable_capturing = json.getBool("enable_capturing");
    enable_live_all_samples = json.getBool("enable_live_all_samples");
    enable_live_fixed_rate = json.getBool("enable_live_fixed_rate");
    live_rate_hz = json.getFloat("live_rate_hz");
    if(live_rate_hz > 0.0001f) fixed_delta_time = 1.0f / live_rate_hz;
}

