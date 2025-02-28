#include "MultiConnectionManager.h"
#include "NetworkMessages.h"
#include "TimeSource.h"
#include <iostream>

MultiConnectionManager::MultiConnectionManager(EnvConfig* env_config, std::string node_name, std::string hostname, Logger* logger) : 
    ConnectionManager(env_config, node_name, hostname, logger)
{
    //log connection manager node name
    logger->debug(log_prefix + std::string("Creating. Node Name: ") + node_name);

    //create local connection manager
    ZMQConnectionManager* cm = new ZMQConnectionManager(env_config, node_name, hostname, logger);
    cm->set_db_id(env_config->get("DB_ID"));
    connection_managers.push_back(cm);
}

MultiConnectionManager::~MultiConnectionManager()
{
    //log shutdown
    logger->debug(log_prefix + std::string("Shutdown"));

    //delete all connection managers
    for(unsigned int i = 0; i < connection_managers.size(); i++)
    {
        delete connection_managers[i];
    }

    //clear connection manager list
    connection_managers.clear();

    //log done
    logger->debug(log_prefix + std::string("Shutdown done!"));
}

std::string MultiConnectionManager::query(std::string identity, std::string topic, std::string data, double timeout)
{
    return connection_managers[0]->query(identity, topic, data, timeout);
}

void MultiConnectionManager::declare_queryable(std::string topic, INetworkQueryable* queryable_interface)
{
    connection_managers[0]->declare_queryable(topic, queryable_interface);
}

void MultiConnectionManager::subscribe(std::string key, INetworkSubscriber* subscriber_interface)
{
    //get db_id from key
    std::string id = extract_db_id(key);

    //search matching connection manager
    for(unsigned int i = 0; i < connection_managers.size(); i++)
    {
        ConnectionManager* cm = connection_managers[i];

        if(cm->get_db_id() == id) 
        {
            cm->subscribe(key, subscriber_interface);
            return;
        }
    }

    logger->error(log_prefix + std::string("Subscribe for unknown db_id with key: ") + key);
    return;
}

void MultiConnectionManager::unsubscribe(std::string key, INetworkSubscriber* subscriber_interface)
{
    //get db_id from key
    std::string id = extract_db_id(key);

    //search matching connection manager
    for(unsigned int i = 0; i < connection_managers.size(); i++)
    {
        ConnectionManager* cm = connection_managers[i];

        if(cm->get_db_id() == id) 
        {
            cm->unsubscribe(key, subscriber_interface);
            return;
        }
    }

    //there has to be a connection manager for unsubscribe
    logger->error(log_prefix + std::string("Unsubscribe for unknown db_id with key: ") + key);
    return;
}

void MultiConnectionManager::publish(std::string key, std::string data)
{
    //get db_id from key
    std::string id = extract_db_id(key);

    //search matching connection manager
    for(unsigned int i = 0; i < connection_managers.size(); i++)
    {
        ConnectionManager* cm = connection_managers[i];

        if(cm->get_db_id() == id)
        {
            cm->publish(key, data);
            return;
        }
    }

    logger->error(log_prefix + std::string("Publish for unknown db_id with key: ") + key);
    return;
}

std::string MultiConnectionManager::extract_db_id(std::string str)
{
    size_t pos = str.find('/');
    return (pos != std::string::npos) ? str.substr(0, pos) : str;
}

void MultiConnectionManager::set_external_databeams(std::vector<std::string> db_id_list, std::vector<std::string> hostname_list)
{
    //call base implementation to log lists
    ConnectionManager::set_external_databeams(db_id_list, hostname_list);

    //add connection managers for external databeams
    for(unsigned int i = 0; i < hostname_list.size(); i++)
    {
        ZMQConnectionManager* cm = new ZMQConnectionManager(env_config, node_name, hostname_list[i], logger);
        cm->set_db_id(db_id_list[i]);
        connection_managers.push_back(cm);
    }
}