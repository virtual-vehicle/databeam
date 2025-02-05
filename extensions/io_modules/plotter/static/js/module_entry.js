class ModuleEntry
{
  constructor(module_name, module_meta, live_source)
  {
    this.name = module_name
    this.meta = module_meta
    this.live_source = live_source
  }

  getName() { return this.name }
  getMeta() { return this.meta }
  getLiveSource() { return this.live_source }

  setLiveSource(live_source) { this.live_source = live_source }
}