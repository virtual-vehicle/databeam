#include "TimeSource.h"
#include <chrono>
#include <iomanip>
#include <sstream>

long long TimeSource::now()
{
    return std::chrono::time_point_cast<std::chrono::nanoseconds>(
        std::chrono::system_clock::now()).time_since_epoch().count();
}

std::string TimeSource::now_str()
{
    //get current time point
    const std::chrono::time_point<std::chrono::system_clock> now =
        std::chrono::system_clock::now();
 
    //get time_t from time_point
    const std::time_t t_c = std::chrono::system_clock::to_time_t(now);

    //string stream for time string
    std::stringstream ss;

    //get time since epoch
    std::chrono::system_clock::duration time_since_epoch = now.time_since_epoch();

    //get remaining milliseconds
    std::chrono::milliseconds ms = std::chrono::duration_cast<std::chrono::milliseconds>(time_since_epoch) % 1000;

    //construct time string
    ss << std::put_time(std::gmtime(&t_c), "%F %T") << "," << std::setfill('0') << std::setw(3) << ms.count();

    //return time string
    return ss.str();
}

std::string TimeSource::now_time_only_str()
{
    //get current time point
    const std::chrono::time_point<std::chrono::system_clock> now =
        std::chrono::system_clock::now();
 
    //get time_t from time_point
    const std::time_t t_c = std::chrono::system_clock::to_time_t(now);

    //string stream for time string
    std::stringstream ss;

    //get time since epoch
    std::chrono::system_clock::duration time_since_epoch = now.time_since_epoch();

    //get remaining milliseconds
    std::chrono::milliseconds ms = std::chrono::duration_cast<std::chrono::milliseconds>(time_since_epoch) % 1000;

    //construct time string
    ss << std::put_time(std::gmtime(&t_c), "%T") << "." << std::setfill('0') << std::setw(3) << ms.count();

    //return time string
    return ss.str();
}