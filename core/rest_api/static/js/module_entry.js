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
    this.capture = data.enable_capturing
    this.all = data.enable_live_all_samples
    this.fixed = data.enable_live_fixed_rate
    this.fixed_rate = data.live_rate_hz
    this.ready = true
  }

  getName() { return this.name }
  getType() { return this.type }
  getCapture() { return this.capture }
  getAll() { return this.all }
  getFixed() { return this.fixed }
  getFixedRate() { return this.fixed_rate }
  getReady() { return this.ready }

  setReady(ready) { this.ready = ready }

  getDataConfigDict()
  {
    return {
      enable_capturing: this.capture,
      enable_live_all_samples: this.all,
      enable_live_fixed_rate: this.fixed,
      live_rate_hz: this.fixed_rate
    }
  }
}