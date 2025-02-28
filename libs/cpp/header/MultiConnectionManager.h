
#pragma once
#include <string>
#include "EnvConfig.h"
#include "Logger.h"
#include "ConnectionManager.h"
#include "ZMQConnectionManager.h"
#include <unordered_map>
#include <vector>

class MultiConnectionManager : public ConnectionManager
{
public:
    MultiConnectionManager() = delete;
    MultiConnectionManager(EnvConfig* env_config, std::string node_name, std::string hostname, Logger* logger);
    ~MultiConnectionManager();

    void declare_queryable(std::string topic, INetworkQueryable* queryable_interface) override;
    void subscribe(std::string key, INetworkSubscriber* subscriber_interface) override;
    void unsubscribe(std::string key, INetworkSubscriber* subscriber_interface) override;
    void publish(std::string key, std::string data) override;
    std::string query(std::string identity, std::string topic, std::string data, double timeout = 1.0) override;
    void set_external_databeams(std::vector<std::string> db_id_list, std::vector<std::string> hostname_list) override;

private:
    std::string extract_db_id(std::string str);

    //log prefix for this connection manager
    std::string log_prefix = "[Multi CM] ";

    //holds all connection managers
    std::vector<ZMQConnectionManager*> connection_managers;
};