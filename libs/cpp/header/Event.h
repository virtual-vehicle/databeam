#pragma once

#include <mutex>
#include <condition_variable>

class Event
{
public:
    bool isSet();
    void set();
    void clear();
    bool wait();
    bool wait(uint32_t timeout_ms);
    bool wait_and_clear();
    bool wait_and_clear(uint32_t timeout_ms);

private:
    std::mutex is_set_lock_;
    bool is_set_ = false;
    std::condition_variable set_trigger_;
};
