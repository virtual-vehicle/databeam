
#pragma once
#include "ConnectionManager.h"
#include <string>
#include "EnvConfig.h"
#include "Logger.h"
#include <zmq.hpp>
#include <thread>
#include <mutex>
#include <unordered_map>
#include <vector>
#include <random>

class ZMQConnectionManager : public ConnectionManager
{
public:
    ZMQConnectionManager() = delete;
    ZMQConnectionManager(EnvConfig* env_config, std::string node_name, std::string hostname, Logger* logger);
    ~ZMQConnectionManager();

    void declare_queryable(std::string topic, INetworkQueryable* queryable_interface) override;
    void subscribe(std::string key, INetworkSubscriber* subscriber_interface) override;
    void unsubscribe(std::string key, INetworkSubscriber* subscriber_interface) override;
    void publish(std::string key, std::string data) override;
    std::string query(std::string identity, std::string topic, std::string data, double timeout = 1.0) override;

private:
    void queryable_worker();
    void subscribe_worker();
    void stop_subscribe_thread();
    void start_subscribe_thread();
    bool receive_multipart(zmq::socket_t* zmq_socket, std::string* parts, unsigned int num_parts);
    std::string generate_uuid();

    std::string log_prefix = "[ZMQ CM] ";

    //zmq context instance
    zmq::context_t* zmq_context = nullptr;

    //zmq sockets
    zmq::socket_t* subscribe_socket = nullptr;
    zmq::socket_t* publish_socket = nullptr;
    zmq::socket_t* queryable_socket = nullptr;
    zmq::socket_t* query_socket = nullptr; 

    //subscription worker thread
    std::thread subscribe_thread;
    bool subscribe_thread_kill_flag = false;

    //queryable worker thread
    std::thread queryable_thread;
    bool queryable_thread_kill_flag = false;

    //subscription and queryable maps
    std::unordered_map<std::string, std::vector<INetworkSubscriber*>> subscriber_map;
    std::unordered_map<std::string, INetworkQueryable*> queryable_map;

    //locks
    std::mutex subscribe_lock;
    std::mutex publish_lock;
    std::mutex queryable_lock;
    std::mutex query_lock;
    
    //uuid generator
    std::mt19937 random_gen;
    std::uniform_int_distribution<> random_dist;
    const std::string random_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
};