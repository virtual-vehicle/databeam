class ModuleEntry
{
  //constructor(data)
  //{
  //  this.name = data.name
  //  this.type = data.type
  //}

  constructor(data)
  {
    this.name = data.name
    this.type = data.type
    this.capturing_available = data.capturing_available
    this.live_available = data.live_available
    this.capture = data.enable_capturing
    this.all = data.enable_live_all_samples
    this.fixed = data.enable_live_fixed_rate
    this.fixed_rate = data.live_rate_hz
    this.ready = true
    this.module_meta = data['module_meta']
    this.latest_schema_index = 0

    this.mcap_topics = []
    if(Object.hasOwn(this.module_meta, "_mcap_topics")) this.mcap_topics = this.module_meta['_mcap_topics']

    this.webinterfaces = []
    if(Object.hasOwn(this.module_meta, "_webinterfaces")) this.webinterfaces = this.module_meta['_webinterfaces']

    this.video_streams = []
    if(Object.hasOwn(this.module_meta, "_video_streams")) this.video_streams = this.module_meta['_video_streams']

    // console.log("new ModuleEntry: " + JSON.stringify(data, null, 2))
  }

  getName() { return this.name }
  getType() { return this.type }
  getCapturingAvailable() { return this.capturing_available }
  getLiveAvailable() { return this.live_available }
  getCapture() { return this.capture }
  getAll() { return this.all }
  getFixed() { return this.fixed }
  getFixedRate() { return this.fixed_rate }
  getReady() { return this.ready }
  getLatestSchemaIndex() { return this.latest_schema_index }

  hasMCAPTopics() { return this.mcap_topics.length > 0 }
  getMCAPTopics() { return this.mcap_topics }

  getWebInterfacesList()
  {
    return this.webinterfaces
  }

  getVideoStreamsList()
  {
    return this.video_streams
  }

  setReady(ready) { this.ready = ready }

  setLatestTopic(topic)
  {
    for(let i = 0; i < this.mcap_topics.length; i++)
    {
      if(topic == this.mcap_topics[i])
      {
        this.latest_schema_index = i;
        return
      }
    }

    this.latest_schema_index = 0;
  }

  setLatestSchemaIndex(schema_index)
  {
    schema_index = Math.max(schema_index, 0)
    this.latest_schema_index = schema_index
  }

  getDataConfigDict()
  {
    return {
      capturing_available: this.capturing_available,
      live_available: this.live_available,
      enable_capturing: this.capture,
      enable_live_all_samples: this.all,
      enable_live_fixed_rate: this.fixed,
      live_rate_hz: this.fixed_rate
    }
  }
}