#pragma once

#include <queue>
#include <thread>
#include <mutex>
#include <condition_variable>
 
template <typename T>
class AsyncQueue
{
public:
 
  T pop()
  {
    std::unique_lock<std::mutex> mlock(mutex_);
    while (queue_.empty())
    {
      cond_.wait(mlock);
    }
    auto item = queue_.front();
    queue_.pop();
    return item;
  }

  T popSize(uint32_t &queue_size)
  {
    std::unique_lock<std::mutex> mlock(mutex_);
    while (queue_.empty())
    {
      cond_.wait(mlock);
    }
    auto item = queue_.front();
    queue_.pop();
    queue_size = queue_.size();
    return item;
  }
 
  void push(const T& item)
  {
    std::unique_lock<std::mutex> mlock(mutex_);
    queue_.push(item);
    mlock.unlock();
    cond_.notify_one();
  }

/*
  T front()
  {
    std::unique_lock<std::mutex> mlock(mutex_);

    

    return queue_.size() > 0 ? queue_.front() : nullptr;
  }
  */

  void clear()
  {
    std::unique_lock<std::mutex> mlock(mutex_);
    while(!queue_.empty()) queue_.pop();
  }

  int getSize()
  {
    std::unique_lock<std::mutex> mlock(mutex_);
    return queue_.size();
  }
 
private:
  std::queue<T> queue_;
  std::mutex mutex_;
  std::condition_variable cond_;
};