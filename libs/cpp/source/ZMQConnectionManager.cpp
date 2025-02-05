#include "ZMQConnectionManager.h"
#include "TimeSource.h"
#include <iostream>

ZMQConnectionManager::ZMQConnectionManager(EnvConfig* env_config, std::string node_name, std::string hostname, Logger* logger) :
    ConnectionManager(env_config, node_name, hostname, logger)
{
    //store parameters
    this->env_config = env_config;
    this->node_name = node_name;
    this->logger = logger;

    //initialize random uuid generator
    random_gen = std::mt19937(static_cast<unsigned int>(0));
    random_dist = std::uniform_int_distribution<>(0, random_chars.size() - 1);

    //log connection manager node name
    logger->debug(log_prefix + std::string("Creating. Node Name: ") + node_name);
    
    //create zmq context
    zmq_context = new zmq::context_t(1);

    //create subscription socket
    subscribe_socket = new zmq::socket_t(*zmq_context, zmq::socket_type::sub);
    subscribe_socket->set(zmq::sockopt::linger, 0);
    subscribe_socket->set(zmq::sockopt::rcvtimeo, 100);

    //create publish socket
    publish_socket = new zmq::socket_t(*zmq_context, zmq::socket_type::pub);
    publish_socket->set(zmq::sockopt::linger, 0);
    
    //create query socket
    query_socket = new zmq::socket_t(*zmq_context, zmq::socket_type::dealer);
    query_socket->set(zmq::sockopt::routing_id, node_name);
    query_socket->set(zmq::sockopt::linger, 0);
    query_socket->set(zmq::sockopt::rcvtimeo, 100);

    //create queryable socket
    queryable_socket = new zmq::socket_t(*zmq_context, zmq::socket_type::dealer);
    queryable_socket->set(zmq::sockopt::routing_id, node_name);
    queryable_socket->set(zmq::sockopt::linger, 0);
    queryable_socket->set(zmq::sockopt::rcvtimeo, 100);

    //create socket addresses
    std::string pub_address = "tcp://" + hostname + std::string(":") + 
        env_config->get("DB_ROUTER_SUB_PORT");

    std::string sub_address = "tcp://" + hostname + std::string(":") + 
        env_config->get("DB_ROUTER_PUB_PORT");

    std::string query_address = "tcp://" + hostname + std::string(":") + 
        env_config->get("DB_ROUTER_FRONTEND_PORT");

    std::string queryable_address = "tcp://" + hostname + std::string(":") + 
        env_config->get("DB_ROUTER_BACKEND_PORT");

    //log socket connection addresses
    logger->debug(log_prefix + std::string("Publish: ") + pub_address);
    logger->debug(log_prefix + std::string("Subscribe: ") + sub_address);
    logger->debug(log_prefix + std::string("Query: ") + query_address);
    logger->debug(log_prefix + std::string("Queryable: ") + queryable_address);

    //connect sockets
    subscribe_socket->connect(sub_address);
    publish_socket->connect(pub_address);
    query_socket->connect(query_address);
    queryable_socket->connect(queryable_address);

    //start worker threads
    this->queryable_thread = std::thread(&ZMQConnectionManager::queryable_worker, this);
    this->subscribe_thread = std::thread(&ZMQConnectionManager::subscribe_worker, this);
}

ZMQConnectionManager::~ZMQConnectionManager()
{
    //log shutdown
    logger->debug(log_prefix + std::string("Shutdown"));

    //unsubscribe all
    std::unordered_map<std::string, std::vector<INetworkSubscriber*>>::iterator it;

    for(it = subscriber_map.begin(); it != subscriber_map.end(); ++it)
    {
        subscribe_socket->set(zmq::sockopt::unsubscribe, it->first);
    }

    //kill and join threads
    logger->debug(log_prefix + std::string("Joining threads."));
    queryable_thread_kill_flag = true;
    subscribe_thread_kill_flag = true;
    queryable_thread.join();
    subscribe_thread.join();

    //log socket closing
    logger->debug(log_prefix + std::string("Closing sockets."));

    //close publish socket
    publish_lock.lock();
    publish_socket->close();
    publish_lock.unlock();

    //close subscribe socket
    subscribe_lock.lock();
    subscribe_socket->close();
    subscribe_lock.unlock();

    //close query socket
    query_lock.lock();
    query_socket->close();
    query_lock.unlock();

    //close queryable socket
    queryable_lock.lock();
    queryable_socket->close();
    queryable_lock.unlock();

    //delete zmq context
    logger->debug(log_prefix + std::string("Delete ZMQ context."));
    delete zmq_context;

    //log done
    logger->debug(log_prefix + std::string("Connection Manager done!"));
}

void ZMQConnectionManager::queryable_worker()
{
    //holds received parts
    std::string parts[4];

    while(!queryable_thread_kill_flag)
    {
        bool result = receive_multipart(queryable_socket, parts, 4);

        //try again if there was a timeout or not all parts have been received
        if(!result) continue;

        //acquire queryable lock
        queryable_lock.lock();

        //find queryable interface for given topic
        std::unordered_map<std::string, INetworkQueryable*>::const_iterator it;
        it = queryable_map.find(parts[2]);

        //notify queryable interface
        if(it != queryable_map.end())
        {
            //notify and get reply data
            parts[3] = it->second->notify_queryable(it->first, parts[3]);

            //send reply
            for(unsigned int i = 0; i < 4; i++)
            {
                zmq::message_t message_part(parts[i].data(), parts[i].size());
                queryable_socket->send(message_part, i < 3 ? zmq::send_flags::sndmore : zmq::send_flags::none);
            }
        }
        else
        {
            logger->debug(log_prefix + std::string("Received query for undeclared topic:") + parts[2]);
        }

        //release queryable lock
        queryable_lock.unlock();
    }
}

void ZMQConnectionManager::subscribe_worker()
{
    //holds multipart strings
    std::string parts[2];

    while(!subscribe_thread_kill_flag)
    {
        //try to receive multipart message
        if(!receive_multipart(subscribe_socket, parts, 2)) continue;

        //acquire subscription lock
        subscribe_lock.lock();

        //search for subscriber list in subscriber map with topic as key
        std::unordered_map<std::string, std::vector<INetworkSubscriber*>>::const_iterator it;
        it = subscriber_map.find(parts[0]);

        //notify all subscribers
        if(it != subscriber_map.end())
        {
            for(unsigned int i = 0; i < it->second.size(); i++)
            {
                it->second[i]->notify_subscriber(parts[0], parts[1]);
            }
        }

        //release subscription lock
        subscribe_lock.unlock();
    }
}

bool ZMQConnectionManager::receive_multipart(zmq::socket_t* zmq_socket, std::string* parts, unsigned int num_parts)
{
    //holds number of received parts
    unsigned int num_received = 0;

    //receive num_parts parts
    for(unsigned int i = 0; i < num_parts; i++)
    {
        //receive next part
        zmq::message_t part;
        zmq::recv_result_t result = zmq_socket->recv(part, zmq::recv_flags::none);

        //break if there is a timeout
        if(!result) break;

        //store part in string array
        parts[i] = std::string(static_cast<char*>(part.data()), part.size());

        //count number of received parts
        num_received++;

        //break if there are no more parts to receive
        if(!zmq_socket->get(zmq::sockopt::rcvmore)) break;
    }

    //return true if all parts have been received
    return num_received == num_parts;
}

std::string ZMQConnectionManager::query(std::string identity, std::string topic, std::string data, double timeout)
{
    //acquire query lock
    query_lock.lock();

    //generate uuid for this query
    std::string uuid = generate_uuid();

    //send query
    zmq::message_t identity_message(identity.data(), identity.size());
    zmq::message_t uuid_message(uuid.data(), uuid.size());
    zmq::message_t topic_message(topic.data(), topic.size());
    zmq::message_t data_message(data.data(), data.size());
    query_socket->send(identity_message, zmq::send_flags::sndmore);
    query_socket->send(uuid_message, zmq::send_flags::sndmore);
    query_socket->send(topic_message, zmq::send_flags::sndmore);
    query_socket->send(data_message, zmq::send_flags::none);

    //holds received parts
    std::string parts[4];

    //measure elapsed time for timeout
    TimeSource time_source;
    uint64_t start_time = (uint64_t)time_source.now();
    double elapsed_time = 0;

    //while there is no timeout
    while(elapsed_time < timeout)
    {
        //if all parts have been received
        if(receive_multipart(query_socket, parts, 4))
        {
            //check if message was received with given uuid
            if(parts[1] == uuid)
            {
                query_lock.unlock();
                return parts[3];
            }
        }

        //update elapsed time and try again
        elapsed_time = ((double)((uint64_t)time_source.now() - start_time)) * 0.000000001;
    }

    logger->debug("Query Timeout.");
    query_lock.unlock();
    return "";
}

void ZMQConnectionManager::declare_queryable(std::string topic, INetworkQueryable* queryable_interface)
{
    //acquire queryable lock
    queryable_lock.lock();

    //find topic in map
    std::unordered_map<std::string, INetworkQueryable*>::iterator it;
    it = queryable_map.find(topic);

    //make sure topic is only declared once
    if(it == queryable_map.end())
    {
        queryable_map[topic] = queryable_interface;
    }
    else
    {
        logger->error(std::string("Queryable for topic ") + topic + std::string(" already declared."));
    }

    //release queryable lock
    queryable_lock.unlock();
}

void ZMQConnectionManager::subscribe(std::string key, INetworkSubscriber* subscriber_interface)
{
    //acquire subscription lock
    subscribe_lock.lock();

    //find key in subscriber map
    std::unordered_map<std::string, std::vector<INetworkSubscriber*>>::iterator it;
    it = subscriber_map.find(key);

    //if this is the first subscription to this topic
    if(it == subscriber_map.end())
    {
        //subscribe to topic and push subscriber interface to list
        subscribe_socket->set(zmq::sockopt::subscribe, key);
        subscriber_map[key].push_back(subscriber_interface);
    }
    else
    {
        //add subscriber interface only once
        if(std::find(it->second.begin(), it->second.end(), subscriber_interface) == it->second.end())
        {
            it->second.push_back(subscriber_interface);
        }
    }

    //release subscription lock
    subscribe_lock.unlock();
}

void ZMQConnectionManager::unsubscribe(std::string key, INetworkSubscriber* subscriber_interface)
{
    //acquire subscription lock
    subscribe_lock.lock();

    //find key in subscriber map
    std::unordered_map<std::string, std::vector<INetworkSubscriber*>>::iterator it;
    it = subscriber_map.find(key);

    //holds if interface has been found
    bool found = false;

    //if this is the first subscription to this topic
    if(it != subscriber_map.end())
    {
        //remove subscriber from list
        for(unsigned int i = 0; i < it->second.size(); i++)
        {
            if(it->second[i] == subscriber_interface)
            {
                //swap and pop
                it->second[i] = it->second[it->second.size() - 1];
                it->second.pop_back();
                found = true;
                break;
            }
        }

        //if there is no more subscriber for key then unsubscibe and remove list from map
        if(it->second.size() == 0)
        {
            subscribe_socket->set(zmq::sockopt::unsubscribe, key);
            subscriber_map.erase(it);
        }
    }

    //log error if interface was not found
    if(!found) logger->error(std::string("Could not unsubscribe interface for key ") + key);

    //release subscription lock
    subscribe_lock.unlock();
}

void ZMQConnectionManager::publish(std::string key, std::string data)
{
    //acquire publish lock
    publish_lock.lock();

    //send key
    zmq::message_t key_message(key.data(), key.size());
    publish_socket->send(key_message, zmq::send_flags::sndmore);

    //send data
    zmq::message_t data_message(data.data(), data.size());
    publish_socket->send(data_message, zmq::send_flags::none);

    //release publish lock
    publish_lock.unlock();
}

std::string ZMQConnectionManager::generate_uuid()
{
    std::string uuid = "";

    for(unsigned int i = 0; i < 8; i++)
    {
        uuid += random_chars[random_dist(random_gen)];
    }

    return uuid;
}