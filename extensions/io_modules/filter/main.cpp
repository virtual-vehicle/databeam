#include <stdio.h>
#include <string.h>
#include <iostream>
#include "EnvConfig.h"
#include "Logger.h"
#include <csignal>
#include "ModuleInterface.h"
#include "filter.h"
#include "Utils.h"

int main(int argc, char **argv) 
{
  //create environment config
  EnvConfig env_config;

  //add expected environment variables with default values
  env_config.add("MODULE_NAME", "Filter");
  env_config.add("LOGLEVEL", "DEBUG");
  env_config.add("DATA_DIR", "/opt/databeam/data");
  env_config.add("CONFIG_DIR", "/opt/databeam/config");
  env_config.add("DEPLOY_VERSION", "latest");
  env_config.add("DB_ID", "db");
  env_config.add("DB_ROUTER", "localhost");
  env_config.add("DB_ROUTER_FRONTEND_PORT", "5555");
  env_config.add("DB_ROUTER_BACKEND_PORT", "5556");
  env_config.add("DB_ROUTER_SUB_PORT", "5557");
  env_config.add("DB_ROUTER_PUB_PORT", "5558");

  //create and init logger instance
  Logger logger;
  logger.setLogLevel(env_config.get("LOGLEVEL"));
  logger.setName(env_config.get("MODULE_NAME"));

  // create io module sensor
  FilterModule io_module(&env_config);

  //create module interface
  ModuleInterface module_interface(&io_module, &env_config, &logger);

  //run module interface
  module_interface.run();
}
