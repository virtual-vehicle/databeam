#include "ModuleInterface.h"
#include "EnvConfig.h"
#include "Utils.h"
#include "NetworkMessages.h"
#include <string>
#include <iostream>
#include "JsonWriter.h"
#include "TimeSource.h"
#include <csignal>
#include <vector>
#include <filesystem>
#include <regex>

bool ModuleInterface::signal_received = false;

ModuleInterface::ModuleInterface(IOModule* io_module, EnvConfig* env_config, Logger* logger)
{
  //store parameters
  this->env_config = env_config;
  this->logger = logger;
  this->io_module = io_module;

  //store module name and type
  module_name = io_module->getName();
  module_type = io_module->getType();

  //create directory and file paths
  data_dir = env_config->get("DATA_DIR") + "/" + env_config->get("DEPLOY_VERSION");
  config_dir = env_config->get("CONFIG_DIR") + "/" + env_config->get("DEPLOY_VERSION");
  module_config_dir = config_dir + "/" + module_type + "-" + module_name;
  module_config_file = module_config_dir + "/config.json";
  module_data_config_file = module_config_dir + "/data_config.json";

  //read module_documentation
  Utils::read_file_to_string("./../documentation.html", module_documentation);

  //escape module documentation such that it can be sent as json string field
  module_documentation = Utils::escapeJsonString(module_documentation);

  //create connection_manager client
  if (env_config->get("DB_ID").size() <= 0) throw std::runtime_error("DB_ID not set");
  this->connection_manager = (ConnectionManager*) 
    new MultiConnectionManager(env_config, env_config->get("DB_ID") + "/m/" + module_name, env_config->get("DB_ROUTER"), logger);

  //init job manager
  job_manager.init(this->connection_manager, env_config->get("DB_ID"), logger);

  //init ready job
  ready_job.init(&job_manager);
  ready_job.set_module_name(module_name);
  
  //leave if shutdown signal was set
  if(signal_received) return;

  //init data config
  data_config.init(module_data_config_file);

  //init data broker
  data_broker.init(this->connection_manager, &data_config, logger, env_config->get("DB_ID"), module_name);

  //wait for controller
  wait_for_controller();

  //fetch external databeams list
  ExternalDataBeamQuery databeam_query;
  std::string reply_data = connection_manager->query(
    env_config->get("DB_ID") + "/c", "databeam_registry", databeam_query.serialize());
  
  if(reply_data != "")
  {
    ExternalDataBeamQueryReply reply;
    reply.deserialize(reply_data);
    connection_manager->set_external_databeams(reply.db_id_list, reply.hostname_list);
  }
  else
  {
    logger->error("Could not fetch external databeams list from controller.");
  }

  //leave if shutdown signal was set
  if(signal_received) return;

  //prepare the module
  prepare_module();

  //declare queryables and subscribers
  logger->debug("Connect: Declare queryables and subscribers.");
  connection_manager->declare_queryable("config", this);
  connection_manager->declare_queryable("config_event", this);
  connection_manager->declare_queryable("data_config", this);
  connection_manager->declare_queryable("sampling", this);
  connection_manager->declare_queryable("get_docu", this);
  connection_manager->declare_queryable("prepare_sampling", this);
  connection_manager->declare_queryable("prepare_capture", this);
  connection_manager->declare_queryable("get_latest", this);
  connection_manager->declare_queryable("ping", this);
  connection_manager->declare_queryable("get_metadata", this);
  connection_manager->declare_queryable("get_schemas", this);
  connection_manager->declare_queryable("stop_sampling", this);
  connection_manager->declare_queryable("stop_capture", this);
  connection_manager->subscribe(env_config->get("DB_ID") + "/m/" + module_name + "/event_in", this);
  connection_manager->subscribe(env_config->get("DB_ID") + "/c/bc/start_capture", this);
  connection_manager->subscribe(env_config->get("DB_ID") + "/c/bc/start_sampling", this);
  logger->debug("Successfully declared queryables and subcriptions.");
}

ModuleInterface::~ModuleInterface()
{
  if(this->connection_manager != nullptr) delete this->connection_manager;
  this->connection_manager = nullptr;
}

void ModuleInterface::set_ready_state(bool ready_state)
{
  if(ready_job.get_ready() == ready_state) return;
  ready_job.set_ready(ready_state);
  ready_job.update();
}

void ModuleInterface::log_gui(std::string title, std::string message)
{
  job_manager.log_gui(title, message);
}

void ModuleInterface::shutdown()
{
  //log shutdown
  logger->debug("Module Shutdown.");

  //set ready job to done and update
  ready_job.set_done(true);
  ready_job.update();

  //shutdown job manager
  job_manager.shutdown();

  if(data_broker.getSamplingRunning())
  {
    data_broker.stopSampling();
    io_module->prepareStopSampling();
    io_module->stopSampling();
  }

  //stop capture if running
  if(data_broker.getCaptureRunning())
  {
    io_module->prepareStopCapture();
    io_module->stopCapture();
    data_broker.stopCapture();
  }

  //unregister from controller
  unregister_module();

  //shutdown data broker
  data_broker.shutdown();

  //shutdown connection_manager
  if(this->connection_manager != nullptr) delete this->connection_manager;
  this->connection_manager = nullptr;

  //exit program
  exit(0);
}

void ModuleInterface::prepare_module()
{
  //create module config directory
  Utils::create_directory(module_config_dir);

  //read stored module config (if exists)
  std::string module_cfg_str = "";
  Utils::read_file_to_string(module_config_file, module_cfg_str);

  //store default config if config does not exist yet
  if(module_cfg_str == "")
  {
    module_cfg_str = io_module->getDefaultConfig();
    Utils::write_string_to_file(module_config_file, module_cfg_str);
  }

  //initialize module
  this->io_module->init(this, logger, &data_broker);

  //set config
  Json json(module_cfg_str);
  if(this->io_module->setConfig(json) != "") logger->error("Error on initial setConfig");

  //set schemas for data broker
  std::vector<McapSchema> mcap_schemas = this->io_module->getMcapSchemas();
  data_broker.setSchemas(mcap_schemas);
}

void ModuleInterface::wait_for_controller()
{
  logger->debug("Wait for controller...");
  std::string payload = "";
  std::string reply_payload = "";

  while(!signal_received)
  {
    logger->debug("Ping Controller");
    reply_payload = connection_manager->query(env_config->get("DB_ID") + "/c", "ping", payload);

    if(reply_payload.size() > 0)
    {
      logger->debug(std::string("Wait For Controller: ") + reply_payload);
      return;
    }
    else
    {
      logger->error(std::string("Wait For Controller: No Response"));
      sleep(1);
    }
  }
}

void ModuleInterface::register_module()
{
  //create module message with name and type
  Module m(module_name, module_type);

  //create module registry query message
  ModuleRegistryQuery module_registry_query(ModuleRegistryQueryCmd::REGISTER, m);
  std::string message_str = module_registry_query.serialize();

  //send message to controller and get reply
  std::string reply_payload;
  reply_payload = connection_manager->query(env_config->get("DB_ID") + "/c", "module_registry", message_str);

  //check reply status
  if(reply_payload.size() > 0)
  {
    ModuleRegistryReply reply;
    reply.deserialize(reply_payload);

    if(!reply.status.error)
    {
      logger->debug("Module registered.");
    }
  }
  else
  {
    logger->error("Register: Could not reach controller.");
  }
}

void ModuleInterface::unregister_module()
{
  //log module unregister
  logger->debug("Unregister module.");

  //create module message with name and type
  Module m(module_name, module_type);

  //create module registry query message
  ModuleRegistryQuery module_registry_query(ModuleRegistryQueryCmd::REMOVE, m);

  //serialize message
  std::string message_str = module_registry_query.serialize();

  //send message to controller and get reply
  std::string reply_payload;
  reply_payload = connection_manager->query(env_config->get("DB_ID") + "/c", "module_registry", message_str);

  //check reply status
  if(reply_payload.size() > 0)
  {
    ModuleRegistryReply reply;
    reply.deserialize(reply_payload);

    if(reply.status.error)
    {
      logger->error("Error on unregister module.");
    }
    else
    {
      logger->debug("Module unregistered.");
    }
  }
  else
  {
    logger->error("Unregister: Could not reach controller.");
  }
}

void ModuleInterface::notify_subscriber(std::string key, std::string payload)
{
  //split subject
  std::vector<std::string> tokens;
  Utils::split(key, tokens, '/');

  if(tokens.size() >= 4 && tokens[3] == "start_capture")
  {
    //parse message
    StartStop start_stop;
    start_stop.deserialize(payload);

    if(start_stop.cmd == StartStopCmd::START)
    {
      if(!data_broker.getCaptureRunning())
      {
        data_broker.startCapture();
        logger->debug("[Capture/Start] Capture started.");

        if(!data_broker.getSamplingRunning())
        {
          data_broker.startSampling();
          io_module->startSampling();
          logger->debug("[Capture/Start] Sampling started.");
        }
      }
      else
      {
        logger->debug("[Capture/Start] Capture already running.");
      }
    }
    else
    {
      logger->error("Received capture startstop command UNSPECIFIED.");
    }
  }
  else if(tokens.size() >= 4 && tokens[3] == "start_sampling")
  {
    //parse message
    StartStop start_stop;
    start_stop.deserialize(payload);

    if(start_stop.cmd == StartStopCmd::START)
    {
      if(!data_broker.getSamplingRunning())
      {
        data_broker.startSampling();
        io_module->startSampling();
        logger->debug("[Sampling/Start] Sampling started.");
      }
      else
      {
        logger->debug("[Sampling/Start] Sampling already running.");
      }
    }
    else
    {
      logger->error("Received sampling startstop command UNSPECIFIED.");
    }
  }
  else
  {
    logger->error(std::string("Received unknown subscription for key: ") + key);
  }
  
}

//void ModuleInterface::queryable_handler(z_loaned_query_t* query, std::string key, std::string payload)
std::string ModuleInterface::notify_queryable(std::string topic, std::string payload)
{
  if(topic == "ping")
  {
    std::string reply("pong");
    return reply;
  }
  else if(topic == "stop_sampling")
  {
    //parse message
    StartStop start_stop;
    start_stop.deserialize(payload);
    bool error = false;

    if(start_stop.cmd == StartStopCmd::STOP)
    {
      if(data_broker.getSamplingRunning())
      {
        data_broker.stopSampling();
        io_module->prepareStopSampling();
        io_module->stopSampling();
        logger->debug("[Sampling/Stop] Sampling stopped.");
      }
      else
      {
        logger->debug("[Sampling/Stop] Sampling not running.");
        error = true;
      }
    }
    else
    {
      logger->error("Received sampling startstop command UNSPECIFIED.");
      error = true;
    }

    //reply with StartStopReply / status
    Status status(error);
    StartStopReply reply(status);
    std::string reply_str = reply.serialize();
    return reply_str;
  }
  else if(topic == "stop_capture")
  {
    //parse message
    StartStop start_stop;
    start_stop.deserialize(payload);
    bool error = false;

    if(start_stop.cmd == StartStopCmd::STOP)
    {
      if(data_broker.getCaptureRunning())
      {
        data_broker.stopCapture();
        logger->debug("[Capture/Stop] Capture stopped.");

        if(!sampling_before_capture && data_broker.getSamplingRunning())
        {
          data_broker.stopSampling();
          io_module->prepareStopSampling();
          io_module->stopSampling();
          logger->debug("[Sampling/Stop] Sampling stopped.");
        }

        sampling_before_capture = false;
      }
      else
      {
        logger->debug("[Capture/Stop] Capture not running.");
        error = true;
      }
    }
    else
    {
      logger->error("Received capture startstop command UNSPECIFIED.");
      error = true;
    }

    //reply with StartStopReply / status
    Status status(error);
    StartStopReply reply(status);
    std::string reply_str = reply.serialize();
    return reply_str;
  }
  else if(topic == "data_config")
  {
    //parse message
    ModuleDataConfigQuery data_config_query;
    data_config_query.deserialize(payload);

    if(data_config_query.cmd == ModuleDataConfigCmd::GET)
    {
      logger->debug("DataConfig GET");
      Status status(false);
      ModuleDataConfig module_data_config;
      data_config.getReply(&module_data_config);
      ModuleDataConfigReply module_data_config_reply(status, module_data_config);
      std::string data_config_reply_str = module_data_config_reply.serialize();
      return data_config_reply_str;
    }
    else if(data_config_query.cmd == ModuleDataConfigCmd::SET)
    {
      logger->debug("DataConfig SET"); //TODO store new data config
      data_config.store(&data_config_query);
      Status status(false);
      ModuleDataConfigReply module_data_config_reply(status);
      std::string data_config_reply_str = module_data_config_reply.serialize();
      return data_config_reply_str;
    }
    else
    {
      logger->debug("DataConfig UNSPECIFIED");
    }
  }
  else if(topic == "config")
  {
    //parse message
    ModuleConfigQuery module_config_query;
    module_config_query.deserialize(payload);

    if(module_config_query.cmd == ModuleConfigQueryCmd::SET)
    {
      logger->debug("Set Config.");

      //read and apply config
      std::string config_json_str = module_config_query.cfg_json;
      Json json(config_json_str);
      std::string set_config_result = io_module->setConfig(json);

      //store new config if apply was ok
      if (set_config_result.length() == 0) {
        bool write_config = !check_config_path(true) || hasConfigChanged(json);
        if(write_config)
        {
          Utils::write_string_to_file(module_config_file, json.stringify_pretty());
          backupTimestampedConfig(10, json);
        }
      }

      Status status(set_config_result.length() != 0, "Set Config", set_config_result);
      ModuleConfigReply reply(status);
      std::string reply_str = reply.serialize();
      return reply_str;
    }
    else if(module_config_query.cmd == ModuleConfigQueryCmd::GET)
    {
      logger->debug("Get Config.");
      Status status(false);
      ModuleConfigReply reply(status, Utils::escapeJsonString(io_module->getConfig()));
      std::string reply_str = reply.serialize();
      return reply_str;
    }
    else if(module_config_query.cmd == ModuleConfigQueryCmd::GET_DEFAULT)
    {
      logger->debug("Get Default Config.");

      Status status(false);
      ModuleConfigReply reply(status, Utils::escapeJsonString(io_module->getDefaultConfig()));
      std::string reply_str = reply.serialize();
      return reply_str;
    }
    else 
    { 
      logger->debug("Config Query UNSPECIFIED"); 
    }
  }
  else if(topic == "config_event")
  {
    ModuleConfigEvent config_event;
    config_event.deserialize(payload);

    logger->debug("Received config event: " + config_event.cfg_key);
    io_module->configEvent(config_event.cfg_key);

    //send reply
    Status status(false);
    ModuleConfigEventReply reply(status);
    std::string reply_str = reply.serialize();
    return reply_str;
  }
  else if(topic == "prepare_capture")
  {
    if(!data_broker.getCaptureRunning())
    {
      if(!data_broker.getSamplingRunning())
      {
        io_module->prepareStartSampling();
        logger->debug("[Prepare_Capture/Start] Prepare Sampling.");
      }
      else
      {
        sampling_before_capture = true;
      }

      //parse message
      MeasurementInfo measurement_info;
      measurement_info.deserialize(payload);

      //log message
      logger->debug("Received Prepare Capture: Name: " + measurement_info.name + 
        " RunID: " + std::to_string(measurement_info.run_id) +
        " RunTag: " + measurement_info.run_tag);

      //create directory and file paths for current measurement
      module_data_dir = this->data_dir + "/" + measurement_info.name + "/" + this->module_name;
      std::string module_meta_file = module_data_dir + "/module_meta.json";
      std::string module_mcap_file = module_data_dir + "/" + this->module_name + ".mcap";

      //create module directory and write module metadata json file
      Utils::create_directory(module_data_dir);
      Utils::write_string_to_file(module_meta_file, io_module->getMetaDataTemplate());

      //start mcap recording
      std::vector<McapSchema> schema_list = io_module->getMcapSchemas();
      data_broker.prepareCapture(io_module->getName(), io_module->getType(), module_mcap_file, schema_list);
      io_module->prepareStartCapture();

      logger->debug("[Prepare_Capture] Capture prepared.");
    }
    else
    {
      logger->warning("[Prepare_Capture] Capture already running.");
    }

    //reply with status
    Status status(false);
    std::string status_str = status.serialize();
    return status_str;
  }
  else if(topic == "get_latest")
  {
    //reply with latest json data
    std::string latest_json_str = data_broker.getLatestData();
    return latest_json_str;
  }
  else if(topic == "get_schemas")
  {
    //get mcap schemas
    std::vector<McapSchema> mcap_schemas = io_module->getMcapSchemas();
    std::vector<std::string> topic_names;

    //create list of topic names
    for(unsigned int i = 0; i < mcap_schemas.size(); i++)
    {
      topic_names.push_back(mcap_schemas[i].get_topic());
    }

    //create and return reply
    GetSchemasReply get_schemas_reply(topic_names); 
    std::string reply_str = get_schemas_reply.serialize();
    return reply_str;
  }
  else if(topic == "get_docu")
  {
    logger->debug("Received Get Documentation");
    DocumentationReply documentation_reply(module_documentation);
    std::string reply_str = documentation_reply.serialize();
    return reply_str;
  }
  else if(topic == "prepare_sampling")
  {
    //parse message
    StartStop start_stop;
    start_stop.deserialize(payload);

    if(start_stop.cmd == StartStopCmd::START)
    {
      if(!data_broker.getSamplingRunning())
      {
        io_module->prepareStartSampling();
        logger->debug("[Prepare_Sampling/Start] Sampling prepared.");
      }
      else
      {
        logger->warning("[Prepare_Sampling/Start] Sampling already running.");
      }
    }
    else if(start_stop.cmd == StartStopCmd::STOP)
    {
      logger->debug("Received prepare sampling Stop.");
    }
    else
    {
      logger->error("Received sampling startstop command UNSPECIFIED.");
    }

    //reply with StartStopReply / status
    Status status(false);
    StartStopReply reply(status);
    std::string reply_str = reply.serialize();
    return reply_str;
  }
  else if(topic == "get_metadata")
  {
    std::string meta_data = io_module->getMetaDataTemplate();
    return meta_data;
  }
  else
  {
    logger->error("Received unknown query with topic: " + topic);
  }

  return "Received unknown query.";
}

/*
 * Checks if the directory and the file of the config exist.
 * @param repair It true, it creates the directory if it does not exist.
 * @return True if the directory and the file of the config exist.
 */
bool ModuleInterface::check_config_path(bool repair)
{
  auto config_directory_fs = std::filesystem::path(module_config_dir);
  auto config_file_fs = std::filesystem::path(module_config_file);
  if(!std::filesystem::is_directory(config_directory_fs))
  {
    if(repair)
      std::filesystem::create_directory(config_directory_fs);
    return false;
  }

  if(!std::filesystem::is_regular_file(config_file_fs))
    return false;

  return true;
}

/*
 * Checks if the given config json is different to the stored default config file.
 */
bool ModuleInterface::hasConfigChanged(Json& new_config)
{
  std::string old_config_string = "";
  Utils::read_file_to_string(module_config_file, old_config_string);
  if(old_config_string == "")
    return true;
  std::string new_config_string = new_config.stringify_pretty();
  return (old_config_string == new_config_string) == 0;
}

/*
 * Checks if a file string has a timestamp suffix.
 */
bool ModuleInterface::fileIsTimestampedConfig(std::string& config_file_path)
{
  std::regex filename_regex("^config\\.[0-9]{8}_[0-9]{6}\\.json$");
  std::string config_filename;
  Utils::getFileSubstr(config_file_path, config_filename);
  return std::regex_match(config_filename, filename_regex);
}

/*
 * Deletes all config file backups until only <files_to_keep> configs are left.
 */
void ModuleInterface::removeOldConfigs(std::vector<std::string>& filename_list, size_t files_to_keep)
{
  size_t config_file_count = filename_list.size();
  for(const auto& file : filename_list)
  {
    if(config_file_count <= files_to_keep)
      break;

    std::remove(file.c_str());

    config_file_count--;
  }
}

/*
 * Backs up the current config file and deletes old config files.
 */
void ModuleInterface::backupTimestampedConfig(size_t files_to_keep, Json& new_config)
{
  TimeSource time_source;
  std::string time_str = time_source.now_str();
  
  std::string conv_time_str;
  Utils::convertTimestampString(time_str, conv_time_str);

  std::string config_path;
  Utils::getPathSubstr(module_config_file, config_path);

  std::string config_file_backup = config_path + "/" + "config." + conv_time_str + ".json";
  Utils::write_string_to_file(config_file_backup, new_config.stringify_pretty());

  std::vector<std::string> file_list;

  for (const auto& file : std::filesystem::directory_iterator(config_path))
  {
    std::string file_string = file.path();
    if(fileIsTimestampedConfig(file_string))
      file_list.push_back(file_string);
  }

  // Sort the file list to only remove the oldest files with a simple for loop.
  std::sort(file_list.begin(), file_list.end());

  removeOldConfigs(file_list, files_to_keep);
}

void signal_handler(int signum)
{
  std::cout << "\nInterrupt signal (" << signum << ") received.\n";
  ModuleInterface::signal_received = true;
}

void ModuleInterface::run()
{
  // register signal handler
  signal(SIGINT, &signal_handler);
  signal(SIGTERM, &signal_handler);

  wait_for_controller();

  while(!signal_received)
  {
    register_module();
    sleep(1);
  }

  shutdown();
}
