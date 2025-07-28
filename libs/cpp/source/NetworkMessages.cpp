#include "NetworkMessages.h"
#include "JsonWriter.h"
#include "Json.h"

// ===========================================================================
// Status
// ===========================================================================

Status::Status(bool error)
{
    this->error = error;
}

Status::Status(bool error, std::string title, std::string message)
{
    this->error = error;
    this->title = title;
    this->message = message;
}

void Status::serialize(JsonWriter& w)
{
    w.write("error", error);
    w.write("title", title);
    w.write("message", message);
}

std::string Status::serialize()
{
    JsonWriter w;
    w.begin();
    serialize(w);
    w.end();
    return w.getString();
}

void Status::deserialize(std::string json_str)
{
    Json json(json_str);
    this->error = json.getBool("error");
    this->title = json.getString("title");
    this->message = json.getString("message");
}

// ===========================================================================
// ModuleRegistryQuery
// ===========================================================================

Module::Module(std::string name, std::string type)
{
    this->name = name;
    this->type = type;
}

ModuleRegistryQuery::ModuleRegistryQuery(ModuleRegistryQueryCmd cmd, Module module)
{
    this->cmd = cmd;
    this->module = module;
}

std::string ModuleRegistryQuery::serialize()
{
    JsonWriter w;
    w.begin();
    w.write("cmd", static_cast<int>(cmd));
    w.beginObject("module");
    w.write("name", module.name);
    w.write("type", module.type);
    w.endObject();
    w.end();
    return w.getString();
}

void ModuleRegistryReply::deserialize(std::string json_str)
{
    Json json(json_str);
    status.error = json.getNestedBool("/status/error");
    status.title = json.getNestedString("/status/title");
    status.message = json.getNestedString("/status/message");
}

// ===========================================================================
// StartStop
// ===========================================================================

void StartStop::deserialize(std::string json_str)
{
    Json json(json_str);
    cmd = static_cast<StartStopCmd>(json.getInt("cmd"));
}

StartStopReply::StartStopReply(Status status)
{
    this->status = status;
}

std::string StartStopReply::serialize()
{
    JsonWriter w;
    w.begin();
    w.beginObject("status");
    status.serialize(w);
    w.endObject();
    w.end();
    return w.getString();
}

// ===========================================================================
// ModuleDataConfig
// ===========================================================================

ModuleDataConfig::ModuleDataConfig(bool capturing_available, bool live_available, 
    bool enable_capturing, bool enable_live_all_samples, 
    bool enable_live_fixed_rate, float live_rate_hz)
{
    this->capturing_available = capturing_available;
    this->live_available = live_available;
    this->enable_capturing = enable_capturing;
    this->enable_live_all_samples = enable_live_all_samples;
    this->enable_live_fixed_rate = enable_live_fixed_rate;
    this->live_rate_hz = live_rate_hz;
}

ModuleDataConfigQuery::ModuleDataConfigQuery(ModuleDataConfigCmd cmd, ModuleDataConfig module_data_config)
{
    this->cmd = cmd;
    this->module_data_config = module_data_config;
}

void ModuleDataConfigQuery::deserialize(std::string json_str)
{
    Json json(json_str);
    cmd = static_cast<ModuleDataConfigCmd>(json.getInt("cmd"));
    module_data_config.capturing_available = json.getNestedBool("/config/capturing_available", module_data_config.capturing_available);
    module_data_config.live_available = json.getNestedBool("/config/live_available", module_data_config.live_available);
    module_data_config.enable_capturing = json.getNestedBool("/config/enable_capturing");
    module_data_config.enable_live_all_samples = json.getNestedBool("/config/enable_live_all_samples");
    module_data_config.enable_live_fixed_rate = json.getNestedBool("/config/enable_live_fixed_rate");
    module_data_config.live_rate_hz = json.getNestedFloat("/config/live_rate_hz");
}

ModuleDataConfigReply::ModuleDataConfigReply(Status status)
{
    this->status = status;
}

ModuleDataConfigReply::ModuleDataConfigReply(Status status, ModuleDataConfig module_data_config)
{
    this->status = status;
    this->module_data_config = module_data_config;
}

std::string ModuleDataConfigReply::serialize()
{
    JsonWriter w;
    w.begin();
    w.beginObject("status");
        status.serialize(w);
    w.endObject();
    w.beginObject("config");
        w.write("capturing_available", module_data_config.capturing_available);
        w.write("live_available", module_data_config.live_available);
        w.write("enable_capturing", module_data_config.enable_capturing);
        w.write("enable_live_all_samples", module_data_config.enable_live_all_samples);
        w.write("enable_live_fixed_rate", module_data_config.enable_live_fixed_rate);
        w.write("live_rate_hz", module_data_config.live_rate_hz);
    w.endObject();
    w.end();
    return w.getString();
}

// ===========================================================================
// ModuleConfigEvent
// ===========================================================================

ModuleConfigEvent::ModuleConfigEvent(ModuleConfigEventCmd cmd, std::string cfg_key)
{
    this->cmd = cmd;
    this->cfg_key = cfg_key;
}

void ModuleConfigEvent::deserialize(std::string json_str)
{
    Json json(json_str);
    cmd = static_cast<ModuleConfigEventCmd>(json.getInt("cmd"));
    cfg_key = json.getString("cfg_key");
}

ModuleConfigEventReply::ModuleConfigEventReply(Status status)
{
    this->status = status;
}

std::string ModuleConfigEventReply::serialize()
{
    JsonWriter w;
    w.begin();
    w.beginObject("status");
        status.serialize(w);
    w.endObject();
    w.end();
    return w.getString();
}

// ===========================================================================
// ModuleConfigQuery
// ===========================================================================

void ModuleConfigQuery::deserialize(std::string json_str)
{
    Json json(json_str);
    cmd = static_cast<ModuleConfigQueryCmd>(json.getInt("cmd"));
    cfg_json = json.getString("cfg_json");
}

ModuleConfigReply::ModuleConfigReply(Status status)
{
    this->status = status;
}

ModuleConfigReply::ModuleConfigReply(Status status, std::string cfg_json)
{
    this->status = status;
    this->cfg_json = cfg_json;
}

std::string ModuleConfigReply::serialize()
{
    JsonWriter w;
    w.begin();
    w.beginObject("status");
        status.serialize(w);
    w.endObject();
    w.write("json", cfg_json);
    w.end();
    return w.getString();
}

// ===========================================================================
// MeasurementInfo
// ===========================================================================

void MeasurementInfo::deserialize(std::string json_str)
{
    Json json(json_str);
    name = json.getString("name");
    run_id = json.getInt("run_id");
    run_tag = json.getString("run_tag");
}

// ===========================================================================
// DocumentationReply
// ===========================================================================

DocumentationReply::DocumentationReply(std::string html_text)
{
    this->html_text = html_text;
}

std::string DocumentationReply::serialize()
{
    JsonWriter w;
    w.begin();
    w.write("html_text", html_text);
    w.end();
    return w.getString();
}

// ===========================================================================
// GetSchemasReply
// ===========================================================================

GetSchemasReply::GetSchemasReply(std::vector<std::string> topic_names)
{
    this->topic_names = topic_names;
}

std::string GetSchemasReply::serialize()
{
    JsonWriter w;
    w.begin();
    w.write("topic_names", topic_names);
    w.end();
    return w.getString();
}

// ===========================================================================
// ExternalDBIDtoHostname
// ===========================================================================

ExternalDBIDtoHostnameQuery::ExternalDBIDtoHostnameQuery(std::string external_dbid)
{
    this->external_dbid = external_dbid;
}

std::string ExternalDBIDtoHostnameQuery::serialize()
{
    JsonWriter w;
    w.begin();
    w.write("external_dbid", external_dbid);
    w.end();
    return w.getString();
}

void ExternalDBIDtoHostnameReply::deserialize(std::string json_str)
{
    Json json(json_str);
    dbid = json.getString("dbid");
    hostname = json.getString("hostname");
    pub_port = json.getInt("pub_port");
}


// ===========================================================================
// ExternalDataBeamQuery and Reply
// ===========================================================================

std::string ExternalDataBeamQuery::serialize()
{
    return "{}";
}

void ExternalDataBeamQueryReply::deserialize(std::string json_str)
{
    Json json(json_str);
    db_id_list = json.getStringArray("db_id_list");
    hostname_list = json.getStringArray("hostname_list");
}

// ===========================================================================
// ModuleLatestQuery
// ===========================================================================

void ModuleLatestQuery::deserialize(std::string json_str)
{
    Json json(json_str);
    schema_index = json.getInt("schema_index");
}