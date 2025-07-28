class ModuleEntry
{
  constructor(module_name, module_meta, live_source)
  {
    this.name = module_name
    this.meta = module_meta
    this.live_source = live_source

    this.module_name = module_name.split("/")[0]

    this.video_stream_url = ""
  }

  getName() { return this.name }
  getModuleName() { return this.module_name }
  getMeta() { return this.meta }
  getLiveSource() { return this.live_source }

  getVideoStreamURL() { return this.video_stream_url }
  isVideoStream() { return this.video_stream_url != "" }

  setLiveSource(live_source) { this.live_source = live_source }
  setVideoStreamURL(video_stream_url) { this.video_stream_url = video_stream_url}
}