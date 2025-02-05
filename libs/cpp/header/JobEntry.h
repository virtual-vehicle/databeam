#pragma once

#include <string>
#include "Logger.h"
#include "JsonWriter.h"
#include "ConnectionManager.h"
#include "JobManager.h"


class JobEntry
{
public:
    JobEntry(){};
    virtual ~JobEntry() = default;
    void init(JobManager* job_manager);
    void update(bool locking = true);
    void set_done(bool done) {this->done = done;}
    bool get_done(){return this->done;}
    std::string serialize();
    virtual void write_data(JsonWriter& w){};
    virtual void free(){};

protected:
    JobManager* job_manager = nullptr;
    void set_type(const std::string& type) {this->type = type;}

private:
    void update_internal();
    bool is_queued = false;
    Logger* logger = nullptr;
    ConnectionManager* connection_manager = nullptr;
    std::string db_id = "default";
    int id = -1;
    std::string type = "none";
    bool done = false;

    friend class JobManager;
};

class ReadyJob: public JobEntry
{
public:
    ReadyJob(){set_type("ready");}
    void set_module_name(std::string module_name);
    void set_ready(bool ready);
    void write_data(JsonWriter& w) override;
    bool get_ready(){return ready;}

private:
    std::string module_name = "default";
    bool ready = true;
};

class LogJob: public JobEntry
{
public:
    LogJob();
    ~LogJob(){};
    void write_data(JsonWriter& w) override;
    void free() override;
    void set(std::string name, std::string message);

private:
    std::string name = "Name";
    std::string message = "Message";
    std::string time_str = "00:00:00";
};