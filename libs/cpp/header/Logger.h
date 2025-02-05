#pragma once

#include <iostream>
#include <string>
#include <mutex>
#include "TimeSource.h"

class Logger
{
public:
    enum LogLevel
    {
        None = 0,
        Debug = 1,
        Info = 2,
        Warning = 3,
        Error = 4
    };

    Logger();
    explicit Logger(LogLevel log_level);
    ~Logger();

    void setName(std::string name);
    void setLogLevel(LogLevel log_level);
    void setLogLevel(std::string log_level);

    void debug(std::string message);
    void info(std::string message);
    void warning(std::string message);
    void error(std::string message);

private:
    void updateLogPrefix();

    std::string name = "Name";
    std::string debug_prefix = "";
    std::string info_prefix = "";
    std::string warning_prefix = "";
    std::string error_prefix = "";
    LogLevel log_level = LogLevel::Error;

    TimeSource time_source;

    std::mutex logger_lock;
};