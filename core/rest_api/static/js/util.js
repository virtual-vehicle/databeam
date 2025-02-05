
class Util
{
  constructor(job_name, job_description, job_progress, job_done)
  {

  }

  static ByteCountToString(byte_count)
  {
    if(byte_count < 1000) return byte_count.toString() + " B"
    if(byte_count < 1000000) return (byte_count / 1000).toFixed(0).toString() + " kB"
    if(byte_count < 1000000000) return (byte_count / 1000000).toFixed(0).toString() + " MB"
    return (byte_count / 1000000000).toFixed(1).toString() + " GB"
  }
}

