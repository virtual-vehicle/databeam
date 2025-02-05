#pragma once

#include <stdio.h>
#include <string.h>
#include <vector>
#include <condition_variable>
#include <iostream>
#include "Logger.h"

//#define ZENOHCXX_ZENOHC
//#include "zenoh.hxx"
//using namespace zenoh;
#include "zenoh.h"
//#include "zenoh_macros.h"

class IZenohSubscriber {
 public:
  virtual ~IZenohSubscriber(){};
  virtual void subscriber_handler(std::string key, std::string payload) = 0;
};

class IZenohQueryable {
 public:
  virtual ~IZenohQueryable(){};
  virtual void queryable_handler(z_loaned_query_t* query, std::string key, std::string payload) = 0;
};

class ZenohClient
{
public:
  ZenohClient(std::string db_id, std::string zenoh_router, Logger* logger);
  ~ZenohClient();

  void connect();
  bool isConnected();
  void query(std::string query);
  void query(std::string query, std::string payload, std::string &reply_payload);
  void publish(std::string key, std::string data);
  z_owned_subscriber_t declare_subscriber_unregistered(std::string key, IZenohSubscriber* subscriber_interface);
  void declare_subscriber(std::string key, IZenohSubscriber* subscriber_interface);
  void undeclare_all_subscribers();
  void declare_queryable(std::string key, IZenohQueryable* queryable_interface);
  void undeclare_all_queryables();
  void send_reply(const z_loaned_query_t* query, std::string &key, std::string &payload);

private:
  std::string db_id;
  std::string zenoh_router;
  Logger* logger = nullptr;
  z_owned_session_t zs;
  bool connected = false;
  std::vector<z_owned_subscriber_t> subs;
  std::vector<z_owned_queryable_t> queryables;
};