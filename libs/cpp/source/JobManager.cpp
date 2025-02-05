#include "JobManager.h"
#include "JobEntry.h"
#include <unistd.h>

void JobManager::init(ConnectionManager* connection_manager, std::string db_id, Logger* logger)
{
    this->connection_manager = connection_manager;
    this->db_id = db_id;
    this->logger = logger;
    this->job_thread = std::thread(&JobManager::update_worker, this);
}

void JobManager::update(JobEntry* job_entry, bool locking)
{
    if(locking) job_lock.lock();

    if(!job_entry->is_queued)
    {
        job_entry->is_queued = true;
        job_queue.push(job_entry); 
    }

    if(locking) job_lock.unlock();
}

void JobManager::update_worker()
{
    logger->debug("[JobManager] Started Update Worker.");

    while(true)
    {
        //wait for next job
        JobEntry* job = job_queue.pop();

        //kill thread
        if(job == nullptr) break;

        //update job
        logger->debug("[JobManager] Send job");
        job->update_internal();
    }
}

void JobManager::log_gui(std::string name, std::string message)
{
    //lock job lock
    job_lock.lock();

    //holds allocated log job
    LogJob* log_job = nullptr;

    //get a log job from factory or create new one
    if(free_log_jobs.size() == 0)
    {
        log_job = new LogJob();
        log_job->init(this);
    }
    else
    {
        log_job = free_log_jobs.back();
        free_log_jobs.pop_back();
    }

    logger->debug("Num Free LogJobs: " + std::to_string(free_log_jobs.size()));

    //set and update log job
    log_job->set(name, message);
    
    //update without locking as lock is already hold
    log_job->update(false);

    job_lock.unlock();
}

void JobManager::free_log_job(LogJob* log_job)
{
    free_log_jobs.push_back(log_job);
}

void JobManager::shutdown()
{
    job_queue.push(nullptr);
    job_thread.join();
    logger->debug("[JobManager] Joined Update Worker.");
}
