#include "Event.h"
#include <chrono>

bool Event::isSet()
{
    std::lock_guard<std::mutex> lockGuard(this->is_set_lock_);
    return this->is_set_;
}

void Event::set()
{
    this->is_set_lock_.lock();
    this->is_set_ = true;
    this->is_set_lock_.unlock();
    this->set_trigger_.notify_all();
}

void Event::clear()
{
    this->is_set_lock_.lock();
    this->is_set_ = false;
    this->is_set_lock_.unlock();
}

bool Event::wait()
{
    std::unique_lock<std::mutex> set_trigger_unique_lock(this->is_set_lock_);
    this->set_trigger_.wait(set_trigger_unique_lock, [&]{ return this->is_set_; });
    return true;
}

bool Event::wait(uint32_t timeout_ms)
{
    std::unique_lock<std::mutex> set_trigger_unique_lock(this->is_set_lock_);
    bool ev_set = this->set_trigger_.wait_for(set_trigger_unique_lock, std::chrono::milliseconds(timeout_ms), [&]{ return this->is_set_; });
    return ev_set;  // returns false on timeout
}

bool Event::wait_and_clear()
{
    std::unique_lock<std::mutex> set_trigger_unique_lock(this->is_set_lock_);
    this->set_trigger_.wait(set_trigger_unique_lock, [&]{ return this->is_set_; });
    this->is_set_ = false;
    return true;
}

bool Event::wait_and_clear(uint32_t timeout_ms)
{
    std::unique_lock<std::mutex> set_trigger_unique_lock(this->is_set_lock_);
    bool ev_set = this->set_trigger_.wait_for(set_trigger_unique_lock, std::chrono::milliseconds(timeout_ms), [&]{ return this->is_set_; });
    this->is_set_ = false;
    return ev_set;  // returns false on timeout
}
