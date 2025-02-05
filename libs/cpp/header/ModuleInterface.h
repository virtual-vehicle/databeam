#pragma once

#include "Logger.h"
#include "IOModule.h"
#include "DataBroker.h"
#include "DataConfig.h"
#include "JobManager.h"
#include "JobEntry.h"
#include "MultiConnectionManager.h"

class EnvConfig;

class ModuleInterface : public INetworkSubscriber, public INetworkQueryable
{
public:
  ModuleInterface(IOModule* io_module, EnvConfig* env_config, Logger* logger);
  ~ModuleInterface();

  std::string notify_queryable(std::string topic, std::string payload);
  void notify_subscriber(std::string key, std::string payload) override;
  //void subscriber_handler(std::string key, std::string payload) override;
  //void queryable_handler(z_loaned_query_t* query, std::string key, std::string payload) override;
  void prepare_module();
  void wait_for_controller();
  void register_module();
  void unregister_module();
  void shutdown();
  void run();
  ConnectionManager* getConnectionManager() { return connection_manager; }
  std::string getModuleDataDir()
  {
    return module_data_dir;
  }
  bool getCaptureRunning()
  {
    return data_broker.getCaptureRunning();
  }

  void set_ready_state(bool ready_state);
  void log_gui(std::string title, std::string message);

  static bool signal_received;

private:
  ConnectionManager* connection_manager = nullptr;
  EnvConfig* env_config = nullptr;
  Logger* logger = nullptr;
  IOModule* io_module = nullptr;
  DataBroker data_broker;
  DataConfig data_config;
  std::string module_name = "undefined_name";
  std::string module_type = "undefined_type";
  std::string data_dir = "";
  std::string module_data_dir = "";
  std::string config_dir = "";
  std::string module_config_dir = "";
  std::string module_config_file = "";
  std::string module_data_config_file = "";
  std::string module_documentation = "Module Documentation";
  bool sampling_before_capture = false;
  JobManager job_manager;
  ReadyJob ready_job;

  void removeOldConfigs(std::vector<std::string>& filename_list, size_t files_to_keep);
  bool fileIsTimestampedConfig(std::string& config_file_path);
  bool hasConfigChanged(Json& new_config);
  void backupTimestampedConfig(size_t files_to_keep, Json& new_config);
  bool check_config_path(bool repair);
};
