#include "zenoh_client.h"
#include "JsonWriter.h"
#include <iostream>

void data_handler(z_loaned_sample_t *sample, void *arg) 
{
  //get zenoh client instance
  IZenohSubscriber* sub_interface = (IZenohSubscriber*) arg;

  //key to std::string
  z_view_string_t key_string;
  z_keyexpr_as_view_string(z_sample_keyexpr(sample), &key_string);
  char *keystr = (char*)z_string_data(z_loan(key_string));
  std::string key(keystr, (int)z_string_len(z_loan(key_string)));

  // move data into string
  z_owned_string_t payload_string;
  z_bytes_to_string(z_sample_payload(sample), &payload_string);
  // create std::string from payload
  std::string payload(z_string_data(z_loan(payload_string)), z_string_len(z_loan(payload_string)));

  //invoke handler
  sub_interface->subscriber_handler(key, payload);

  //cleanup
  z_drop(z_move(payload_string));
}

void queryable_handler(z_loaned_query_t *query, void *arg) 
{
  //get zenoh client instance
  IZenohQueryable* queryable_interface = (IZenohQueryable*) arg;

  //key to std::string
  z_view_string_t key_string;
  z_keyexpr_as_view_string(z_query_keyexpr(query), &key_string);
  std::string key(z_string_data(z_loan(key_string)), z_string_len(z_loan(key_string)));

  //payload to std::string
  const z_loaned_bytes_t *payload_bytes = z_query_payload(query);

  if(payload_bytes != NULL && z_bytes_len(payload_bytes) > 0)
  {
    // move data into string
    z_owned_string_t payload_string;
    z_bytes_to_string(payload_bytes, &payload_string);
    // create std::string from payload
    std::string payload(z_string_data(z_loan(payload_string)), z_string_len(z_loan(payload_string)));

    //invoke handler
    queryable_interface->queryable_handler(query, key, payload);

    //cleanup
    z_drop(z_move(payload_string));
  }
  else
  {
    queryable_interface->queryable_handler(query, key, "");
  }
}

ZenohClient::ZenohClient(std::string db_id, std::string zenoh_router, Logger* logger)
{
  this->db_id = db_id;
  this->zenoh_router = zenoh_router;
  this->logger = logger;
  logger->debug("Created Zenoh Client. DB_ID: " + this->db_id + ", ZENOH_ROUTER: " + this->zenoh_router);
}

ZenohClient::~ZenohClient()
{
  //log shutdown
  logger->debug("Shutdown Zenoh Client.");

  //unsubscribe
  undeclare_all_queryables();
  undeclare_all_subscribers();

  //close session
  z_drop(z_move(this->zs));
}

void ZenohClient::connect()
{
  z_owned_config_t config;
  z_config_default(&config);
  
  //logger->debug("Zenoh Connect.");

  //create config json
  JsonWriter json_writer;
  json_writer.begin();
  // mode: "client" (brokered via zenoh-router) or "peer" (peer-to-peer mesh)
  json_writer.write("mode", "peer");
  json_writer.beginObject("connect");
  std::vector<std::string> endpoints = {std::string("tcp/") + this->zenoh_router + ":7447"};
  json_writer.write("endpoints", endpoints);
  json_writer.endObject();
  json_writer.beginObject("scouting");
  json_writer.beginObject("multicast");
  json_writer.write("enabled", false);
  json_writer.endObject();
  json_writer.beginObject("gossip");
  json_writer.write("enabled", true);
  json_writer.endObject();
  json_writer.endObject();
  json_writer.end();

  //apply config updates
  std::string config_json_str = json_writer.getString();
  zc_config_from_str(&config, config_json_str.c_str());

  //open zenoh session
  z_result_t result = z_open(&this->zs, z_move(config), NULL);

  //set connected flag
  connected = result == 0;
}

bool ZenohClient::isConnected()
{
  return connected;
}

void ZenohClient::declare_queryable(std::string key, IZenohQueryable* queryable_interface)
{
  //create key expression from string
  z_view_keyexpr_t key_expr;
  z_view_keyexpr_from_str(&key_expr, key.c_str());

  //create callback closure
  z_owned_closure_query_t callback;
  z_closure(&callback, queryable_handler, NULL, (void*)queryable_interface);
  z_owned_queryable_t qable;

  //declare queryable
  z_declare_queryable(z_loan(this->zs), &qable, z_loan(key_expr), z_move(callback), NULL);

  //store queryable
  this->queryables.push_back(qable);
}

void ZenohClient::undeclare_all_queryables()
{
  for(unsigned int i = 0; i < queryables.size(); i++)
  {
    z_drop(z_move(queryables[i]));
  }

  queryables.clear();
}

z_owned_subscriber_t ZenohClient::declare_subscriber_unregistered(std::string key, IZenohSubscriber* subscriber_interface)
{
  z_view_keyexpr_t ke;
  z_view_keyexpr_from_str(&ke, key.c_str());

  z_owned_closure_sample_t callback;
  z_closure(&callback, data_handler, NULL, (void*) subscriber_interface);
  z_owned_subscriber_t sub;
  z_declare_subscriber(z_loan(this->zs), &sub, z_loan(ke), z_move(callback), NULL);
  return sub;
}

void ZenohClient::declare_subscriber(std::string key, IZenohSubscriber* subscriber_interface)
{
  z_owned_subscriber_t sub = declare_subscriber_unregistered(key, subscriber_interface);
  subs.push_back(sub);
}

void ZenohClient::undeclare_all_subscribers()
{
  for(unsigned int i = 0; i < subs.size(); i++)
  {
    z_drop(z_move(subs[i]));
  }

  subs.clear();
}

void ZenohClient::publish(std::string key, std::string data)
{
  //create key expression from string
  z_view_keyexpr_t ke;
  z_view_keyexpr_from_str(&ke, key.c_str());

  z_owned_bytes_t payload;
  z_bytes_copy_from_str(&payload, data.c_str());

  // TODO: create publisher and use z_publisher_put()
  z_put(z_loan(this->zs), z_loan(ke), z_move(payload), NULL);
}

void ZenohClient::query(std::string query, std::string payload, std::string &reply_payload)
{
  reply_payload.clear();

  //create key expression from string
  z_view_keyexpr_t ke;
  z_view_keyexpr_from_str(&ke, query.c_str());

  //create reply fifo channel
  z_owned_fifo_handler_reply_t handler;
  z_owned_closure_reply_t closure;
  z_fifo_channel_reply_new(&closure, &handler, 16);

  z_get_options_t opts;
  z_get_options_default(&opts);

  z_owned_bytes_t pl;
  z_bytes_copy_from_str(&pl, payload.c_str());
  opts.payload = z_move(pl);

  //perform query (opts should ideally passed with z_move)
  z_get(z_loan(this->zs), z_loan(ke), "", z_move(closure), &opts);

  //create reply
  z_owned_reply_t reply;

  //iterate replies
  for (z_result_t res = z_recv(z_loan(handler), &reply); res == Z_OK; res = z_recv(z_loan(handler), &reply)) 
  {
    if (z_reply_is_ok(z_loan(reply))) 
    {
      const z_loaned_sample_t *sample = z_reply_ok(z_loan(reply));

      //get reply payload
      z_owned_string_t reply_str;
      z_bytes_to_string(z_sample_payload(sample), &reply_str);
      // TODO this overwrites reply_payload when receiving multiple replies
      reply_payload = std::string(z_string_data(z_loan(reply_str)), z_string_len(z_loan(reply_str)));

      //cleanup
      z_drop(z_move(reply_str));
      //free reply
      z_drop(z_move(reply));
      break;
    } 
    else 
    {
      logger->debug(std::string("Reply error for query: ") + query);
      break;
    }
  }

  //cleanup handler
  z_drop(z_move(handler));

  return;
}

void ZenohClient::send_reply(const z_loaned_query_t* query, std::string &key, std::string &payload)
{
  //create key expression from string
  z_view_keyexpr_t ke;
  z_view_keyexpr_from_str(&ke, key.c_str());

  //create reply options
  z_query_reply_options_t options;
  z_query_reply_options_default(&options);
  //options.encoding = z_encoding(Z_ENCODING_PREFIX_TEXT_PLAIN, NULL);
  //z_owned_encoding_t encoding;
  //z_encoding_clone(&encoding, z_encoding_text_plain());
  //options.encoding = &encoding;

  //serialize payload string into slice
  z_owned_bytes_t reply_payload;
  z_bytes_from_buf(&reply_payload, (uint8_t*)(payload.data()), payload.length(), NULL, NULL);

  z_query_reply(query, z_loan(ke), z_move(reply_payload), &options);

  //z_drop(z_move(dst));
}