#pragma once

#include <string>
#include <vector>
#include "JsonWriter.h"

// ===========================================================================
// Status
// ===========================================================================

class Status
{
public:
    Status(){};
    explicit Status(bool error);
    Status(bool error, std::string title, std::string message);
    void serialize(JsonWriter& w);
    std::string serialize();
    void deserialize(std::string json_str);

    bool error = false;
    std::string title = "title";
    std::string message = "message";
};

// ===========================================================================
// ModuleRegistryQuery
// ===========================================================================

class Module
{
public:
    Module(){};
    Module(std::string name, std::string type);

    std::string name = "default_name";
    std::string type = "default_type";
};

enum class ModuleRegistryQueryCmd 
{
    UNSPECIFIED = 0,
    REGISTER = 1,
    REMOVE = 2,
    LIST = 3
};

class ModuleRegistryQuery
{
public:
    ModuleRegistryQuery(ModuleRegistryQueryCmd cmd, Module module);
    std::string serialize();

    ModuleRegistryQueryCmd cmd = ModuleRegistryQueryCmd::UNSPECIFIED;
    Module module;
};

class ModuleRegistryReply
{
public:
    ModuleRegistryReply(){};
    void deserialize(std::string json_str);

    Status status;
};

// ===========================================================================
// StartStop
// ===========================================================================

enum class StartStopCmd 
{
    UNSPECIFIED = 0,
    START = 1,
    STOP = 2
};

class StartStop
{
public:
    StartStop(){};
    void deserialize(std::string json_str);

    StartStopCmd cmd = StartStopCmd::UNSPECIFIED;
};

class StartStopReply
{
public:
    StartStopReply(){};
    explicit StartStopReply(Status status);
    
    std::string serialize();

    Status status;
};

// ===========================================================================
// ModuleDataConfigQuery
// ===========================================================================

enum class ModuleDataConfigCmd 
{
    UNSPECIFIED = 0,
    SET = 1,
    GET = 2
};

class ModuleDataConfig
{
public:
    ModuleDataConfig(){}
    ModuleDataConfig(bool enable_capturing, bool enable_live_all_samples, bool enable_live_fixed_rate, float live_rate_hz);

    bool enable_capturing = false;
    bool enable_live_all_samples = false;
    bool enable_live_fixed_rate = false;
    float live_rate_hz = 1.0f;
};

class ModuleDataConfigQuery
{
public:
    ModuleDataConfigQuery(){}
    ModuleDataConfigQuery(ModuleDataConfigCmd cmd, ModuleDataConfig module_data_config);

    void deserialize(std::string json_str);

    ModuleDataConfigCmd cmd = ModuleDataConfigCmd::UNSPECIFIED;
    ModuleDataConfig module_data_config;
};

class ModuleDataConfigReply
{
public:
    ModuleDataConfigReply() = delete;
    explicit ModuleDataConfigReply(Status status);
    ModuleDataConfigReply(Status status, ModuleDataConfig module_data_config);

    std::string serialize();

    Status status;
    ModuleDataConfig module_data_config;
};

// ===========================================================================
// ModuleConfigEvent
// ===========================================================================

enum class ModuleConfigEventCmd 
{
    UNSPECIFIED = 0,
    BUTTON = 1,
};

class ModuleConfigEvent
{
public:
    ModuleConfigEvent(){}
    ModuleConfigEvent(ModuleConfigEventCmd cmd, std::string cfg_key);

    void deserialize(std::string json_str);

    ModuleConfigEventCmd cmd = ModuleConfigEventCmd::UNSPECIFIED;
    std::string cfg_key = "";
};

class ModuleConfigEventReply
{
public:
    ModuleConfigEventReply() = delete;
    ModuleConfigEventReply(Status status);

    std::string serialize();

    Status status;
};

// ===========================================================================
// ModuleConfigQuery
// ===========================================================================

enum class ModuleConfigQueryCmd 
{
    UNSPECIFIED = 0,
    SET = 1,
    GET = 2,
    GET_DEFAULT = 3
};

class ModuleConfigQuery
{
public:
    ModuleConfigQuery(){};
    void deserialize(std::string json_str);

    ModuleConfigQueryCmd cmd = ModuleConfigQueryCmd::UNSPECIFIED;
    std::string cfg_json = "";
};

class ModuleConfigReply
{
public:
    ModuleConfigReply() = delete;
    explicit ModuleConfigReply(Status status);
    ModuleConfigReply(Status status, std::string cfg_json);

    std::string serialize();

    Status status;
    std::string cfg_json = "";
};

// ===========================================================================
// MeasurementInfo
// ===========================================================================

class MeasurementInfo
{
public:
    MeasurementInfo(){};
    void deserialize(std::string json_str);

    std::string name = "";
    int run_id = 0;
    std::string run_tag = "";
};

// ===========================================================================
// DocumentationReply
// ===========================================================================

class DocumentationReply
{
public:
    DocumentationReply() = delete;
    explicit DocumentationReply(std::string html_text);

    std::string serialize();

    std::string html_text = "";
};

// ===========================================================================
// ExternalDBIDtoHostname
// ===========================================================================

class ExternalDBIDtoHostnameQuery
{
public:
    ExternalDBIDtoHostnameQuery() = delete;
    ExternalDBIDtoHostnameQuery(std::string external_dbid);
    
    std::string serialize();

    std::string external_dbid;
};

class ExternalDBIDtoHostnameReply
{
public:
    ExternalDBIDtoHostnameReply(){};

    void deserialize(std::string json_str);

    std::string dbid;
    std::string hostname;
    int pub_port;
};

// ===========================================================================
// ExternalDataBeamQuery and Reply
// ===========================================================================

class ExternalDataBeamQuery
{
public:
    ExternalDataBeamQuery(){};
    std::string serialize();
};

class ExternalDataBeamQueryReply
{
public:
    ExternalDataBeamQueryReply(){};

    void deserialize(std::string json_str);

    std::vector<std::string> db_id_list;
    std::vector<std::string> hostname_list;
};