#include "JobEntry.h"
#include "Json.h"

void JobEntry::init(JobManager* job_manager)
{
    this->job_manager = job_manager;
    this->connection_manager = job_manager->get_connection_manager();
    this->db_id = job_manager->get_db_id();
    this->logger = job_manager->get_logger();
}

void JobEntry::update(bool locking)
{
    job_manager->update(this, locking);
}

void JobEntry::update_internal()
{
    job_manager->get_job_lock()->lock();
    std::string payload = serialize();
    std::string reply_payload = ""; 
    bool done_flag = done;

    // submit job if id is not set
    if(id == -1)
    {
        //perform query, unlock to prevent connection_manager deadlocks
        job_manager->get_job_lock()->unlock();
        reply_payload = connection_manager->query(db_id + "/c", "job_submit", payload);
        job_manager->get_job_lock()->lock();

        if(reply_payload.size() > 0)
        {
            Json json;
            json.parse(reply_payload);

            if(json.has("id"))
            {
                id = json.getInt("id");
            }
            else
            {
                logger->debug(std::string("Error during job update/submit: No id received."));
            }
        }
        else
        {
            logger->debug(std::string("Error during job submit. Received no reply"));
        }
    }
    else //job is already active, update job
    {
        //perform query, unlock to prevent connection_manager deadlocks
        job_manager->get_job_lock()->unlock();
        reply_payload = connection_manager->query(db_id + "/c", "job_update", payload);
        job_manager->get_job_lock()->lock();

        if(reply_payload.size() == 0)
        {
            logger->debug(std::string("Error during job update. Received no reply."));
        }
    }

    // if we have sent the job with the done flag we can reset this job as the job server will clear the job
    if(done_flag) id = -1;
    is_queued = false;
    free();
    job_manager->get_job_lock()->unlock();
}

std::string JobEntry::serialize()
{
    JsonWriter w;
    w.begin();
    w.write("id", id);
    w.write("type", type);
    w.write("done", done);
    w.beginObject("data");
        write_data(w);
    w.endObject();
    w.end();

    return w.getString();
}

void ReadyJob::write_data(JsonWriter& w)
{
    w.write("module_name", module_name);
    w.write("ready", ready);
}

void ReadyJob::set_module_name(std::string module_name) 
{
    job_manager->get_job_lock()->lock();
    this->module_name = module_name;
    job_manager->get_job_lock()->unlock();
}

void ReadyJob::set_ready(bool ready)
{
    job_manager->get_job_lock()->lock();
    this->ready = ready;
    job_manager->get_job_lock()->unlock();
}

LogJob::LogJob()
{
    set_type("log"); 
    set_done(true);
}

void LogJob::write_data(JsonWriter& w)
{
    w.write("name", name);
    w.write("message", message);
    w.write("time_str", time_str);
}

void LogJob::free()
{
    job_manager->free_log_job(this);
}

void LogJob::set(std::string name, std::string message)
{
    TimeSource time_source;

    //locking is handled by job manager!
    this->name = name;
    this->message = message;
    this->time_str = time_source.now_time_only_str();
}