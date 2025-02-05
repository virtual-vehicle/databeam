#include "Logger.h"

Logger::Logger()
{
    updateLogPrefix();
}

Logger::Logger(LogLevel log_level)
{
    this->log_level = log_level;
    updateLogPrefix();
}

Logger::~Logger()
{

}

void Logger::setName(std::string name)
{
    this->name = name;
    updateLogPrefix();
}

void Logger::updateLogPrefix()
{
    this->info_prefix = std::string(   " [INFO   ] [") + name + std::string("] ");
    this->debug_prefix = std::string(  " [DEBUG  ] [") + name + std::string("] ");
    this->warning_prefix = std::string(" [WARNING] [") + name + std::string("] ");
    this->error_prefix = std::string(  " [ERROR  ] [") + name + std::string("] ");
}

void Logger::setLogLevel(LogLevel log_level)
{
    this->log_level = log_level;
    updateLogPrefix();
}

void Logger::setLogLevel(std::string log_level)
{
    if(log_level == "DEBUG") this->log_level = LogLevel::Debug;
    if(log_level == "INFO") this->log_level = LogLevel::Info;
    if(log_level == "WARNING") this->log_level = LogLevel::Warning;
    if(log_level == "ERROR") this->log_level = LogLevel::Error;
    updateLogPrefix();
}

void Logger::debug(std::string message)
{
    if(log_level > LogLevel::Debug) return;
    std::unique_lock<std::mutex> mlock(logger_lock);
    std::cout << time_source.now_str() << debug_prefix << message << std::endl;
}

void Logger::info(std::string message)
{
    if(log_level > LogLevel::Info) return;
    std::unique_lock<std::mutex> mlock(logger_lock);
    std::cout << time_source.now_str() << info_prefix << message << std::endl;
}

void Logger::warning(std::string message)
{
    if(log_level > LogLevel::Warning) return;
    std::unique_lock<std::mutex> mlock(logger_lock);
    std::cout << time_source.now_str() << warning_prefix << message << std::endl;
}

void Logger::error(std::string message)
{
    std::unique_lock<std::mutex> mlock(logger_lock);
    std::cout << time_source.now_str() << error_prefix << message << std::endl;
}