class MeasurementEntry
{
  constructor(data)
  {
    this.name = data.measurement
    this.db_id = data.meta.db_id
    this.modules = data.modules
    this.total_size_bytes = data.total_size_bytes
    this.duration = data.meta.duration
    this.run_tag = data.meta.run_tag
    this.run_id = data.meta.run_id
    this.selected = false

    let date_time_array = this.name.split(".")[0].split("_")
    this.display_name = "&#128203;" + date_time_array[0] + " <wbr>&#128337;" + date_time_array[1].replaceAll("-",":")

    this.display_duration = this.duration.split(".")[0]
    if(this.display_duration == "0:00:00") this.display_duration = "0:00:01"

    this.modules.sort()
    this.display_modules = this.modules.toString().replaceAll(",", ", ")
  }

  getName() { return this.name }
  getDisplayName() { return this.display_name }
  getDatabeamID() { return this.db_id }
  getModules() { return this.modules }
  getTotalSizeBytes() { return this.total_size_bytes }
  getDuration() { return this.duration }
  getDisplayDuration() {return this.display_duration}
  getRunTag() { return this.run_tag }
  getRunID() { return this.run_id }
  getDisplayModules() { return this.display_modules }
  getSelected() { return this.selected }

  setSelected(state) 
  { 
    this.selected = state
  }
}