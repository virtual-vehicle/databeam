#pragma once
#include <string>
//#include "NetworkMessages.h"

class ModuleDataConfigQuery;
class ModuleDataConfig;

class DataConfig
{
public:
    DataConfig();
    ~DataConfig();

    void init(std::string module_data_config_file);
    void store(ModuleDataConfigQuery* data_config_query);
    void getReply(ModuleDataConfig* module_data_config);
    double getFixedDeltaTime();
    bool getFixedEnabled();
    bool getAllEnabled();
    bool getEnableCapturing();
    bool getCapturingAvailable();
    bool getLiveAvailable();

private:
    void storeToFile();
    void readFromFile();

    std::string module_data_config_file = "";
    bool capturing_available = true;
    bool live_available = true;
    bool enable_capturing = true;
    bool enable_live_all_samples = false;
    bool enable_live_fixed_rate = false;
    float live_rate_hz = 1.0f;
    double fixed_delta_time = 1.0f;
};