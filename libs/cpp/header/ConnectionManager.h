
#pragma once
#include <string>
#include "EnvConfig.h"
#include "Logger.h"
#include <zmq.hpp>
#include <thread>
#include <mutex>
#include <unordered_map>
#include <vector>
#include <random>

class INetworkQueryable {
 public:
  virtual ~INetworkQueryable(){};
  virtual std::string notify_queryable(std::string topic, std::string payload) = 0;
};

class INetworkSubscriber {
 public:
  virtual ~INetworkSubscriber(){};
  virtual void notify_subscriber(std::string key, std::string payload) = 0;
};

class ConnectionManager
{
public:
    ConnectionManager() = delete;
    ConnectionManager(EnvConfig* env_config, std::string node_name, std::string hostname, Logger* logger);
    virtual ~ConnectionManager();

    virtual void declare_queryable(std::string topic, INetworkQueryable* queryable_interface) = 0;
    virtual void subscribe(std::string key, INetworkSubscriber* subscriber_interface) = 0;
    virtual void unsubscribe(std::string key, INetworkSubscriber* subscriber_interface) = 0;
    virtual void publish(std::string key, std::string data) = 0;
    virtual std::string query(std::string identity, std::string topic, std::string data, double timeout = 1.0) = 0;

    std::string get_db_id();
    std::string get_host_name();

    void set_db_id(std::string db_id);

    void set_external_databeams(std::vector<std::string> db_id_list, 
        std::vector<std::string> hostname_list);

protected:
    std::string get_external_hostname(std::string db_id);

    //environment config
    EnvConfig* env_config = nullptr;

    //logger reference and prefix
    Logger* logger = nullptr;

    //node name of this connection manager instance
    std::string node_name = "";

    std::string db_id = "dbid";
    std::string hostname = "localhost";

    //list of external databeams
    std::vector<std::string> db_id_list;
    std::vector<std::string> hostname_list;

private:
    std::string log_prefix = "[Base CM] ";
};