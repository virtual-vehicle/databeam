#include "ConnectionManager.h"
#include "TimeSource.h"
#include "Utils.h"
#include <iostream>

ConnectionManager::ConnectionManager(EnvConfig* env_config, std::string node_name, std::string hostname, Logger* logger)
{
    //store parameters
    this->env_config = env_config;
    this->node_name = node_name;
    this->logger = logger;
    this->hostname = hostname;

    //log connection manager node name
    logger->debug(log_prefix + std::string("Base Creating. Node Name: ") + node_name);
}

ConnectionManager::~ConnectionManager()
{
    //log shutdown
    logger->debug(log_prefix + std::string("Base Shutdown"));

    //log done
    logger->debug(log_prefix + std::string("Base Shutdown done!"));
}

std::string ConnectionManager::get_db_id()
{
    return db_id;
}

std::string ConnectionManager::get_host_name()
{
    return hostname;
}

void ConnectionManager::set_db_id(std::string db_id)
{
    this->db_id = db_id;
}

void ConnectionManager::set_external_databeams(std::vector<std::string> db_id_list, std::vector<std::string> hostname_list)
{
    this->db_id_list = db_id_list;
    this->hostname_list = hostname_list;
    logger->debug(log_prefix + std::string("External DB_IDs: ") + Utils::vectorToString(db_id_list));
    logger->debug(log_prefix + std::string("External Hostnames: ") + Utils::vectorToString(hostname_list));
}

std::string ConnectionManager::get_external_hostname(std::string db_id)
{
    for(unsigned int i = 0; i < db_id_list.size(); i++)
    {
        if(db_id_list[i] == db_id) return hostname_list[i];
    }

    return "";
}