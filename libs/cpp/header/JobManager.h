#pragma once

#include "Logger.h"
#include <string>
#include <mutex>
#include <thread>
#include "AsyncQueue.h"
#include <vector>

class JobEntry;
class LogJob;
class ConnectionManager;

class JobManager
{
public:
    JobManager(){};
    void init(ConnectionManager* connection_manager, std::string db_id, Logger* logger);
    
    void shutdown();
    std::mutex* get_job_lock(){return &job_lock;}
    ConnectionManager* get_connection_manager(){return connection_manager;}
    std::string get_db_id(){return db_id;} 
    Logger* get_logger(){return logger;}

    void log_gui(std::string name, std::string message);
    void free_log_job(LogJob* log_job);

private:
    void update(JobEntry* job_entry, bool locking = true);
    void update_worker();
    
    ConnectionManager* connection_manager = nullptr;
    std::string db_id = "default";
    Logger* logger = nullptr;
    std::mutex job_lock;
    std::mutex factory_lock;
    std::thread job_thread;
    AsyncQueue<JobEntry*> job_queue;

    std::vector<LogJob*> free_log_jobs;

    friend class JobEntry;
};