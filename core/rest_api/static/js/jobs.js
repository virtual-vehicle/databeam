
class JobEntry
{
  constructor(job_name, job_description, job_progress, job_done)
  {
    this.name = job_name
    this.description = job_description
    this.progress = Math.max(Math.min(job_progress, 1.0), 0.0)
    this.done = job_done
  }

  getName() { return this.name; }
  getDescription() { return this.description; }
  getProgress() { return this.progress; }
  getDone() { return this.done; }
}

class BusyJob
{
  constructor(job)
  {
    this.name = job.data.name
    this.description = job.data.description
    this.done = job.done
    this.id = job.id
  }

  getName() { return this.name; }
  getDescription() { return this.description; }
  getDone() { return this.done; }
  getID() { return this.id; }
}