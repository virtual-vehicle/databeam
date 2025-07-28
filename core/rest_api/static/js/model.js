class Model {
  constructor() 
  {
    this.databeam_ip = "localhost"
    this.databeam_port = "5000"
    this.ws_port = "5001"
    this.databeam_url = "localhost:5000"
    this.databeam_ws_url = "localhost:5001"
    this.measurements = []
    this.modules = []
    this.system_meta = {}
    this.user_meta = []
    this.client_id = -1
    this.preview_data = undefined
    this.module_documentation = ""
    this.selected_module = ""
    this.online_status = false
    

    //module config
    this.config = ""
    this.config_json = null
    this.config_module_name = ""
    this.config_entries = []
    this.config_dirty = false
    this.root_config_entry = null

    //config layout
    this.config_layout = localStorage.getItem("config_layout")
    if(this.config_layout == null) this.config_layout = "wrap"

    //jobs
    this.jobs = []
    this.busy_jobs = []
    this.databeam_time_ns = 0
    this.databeam_time_str = "00:00:00"
    this.state_job = undefined

    //events
    this.event_modules_changed = false
    this.event_files_changed = false
    this.event_meta_changed = false

    //docker
    this.containers = []
    this.container_log = ""
    this.selected_container_id = ""
    this.docker_log_filter = [true, true, true, true]

    //theme
    this.theme = localStorage.getItem("theme")
    if(this.theme == null) this.theme = "Light"

    //state
    this.capture_running = false
    this.sampling_running = false
  }

  init(controller, view)
  {
    this.controller = controller
    this.view = view
  }

  //setDataBeamURL(databeam_url){ this.databeam_url = databeam_url }
  setDataBeamIP(databeam_ip)
  { 
    this.databeam_ip = databeam_ip 
    this.databeam_url = databeam_ip + ":" + this.databeam_port
    this.databeam_ws_url = databeam_ip + ":" + this.ws_port
  }

  getDataBeamIP() { return "http://" + this.databeam_ip }

  setClientID(client_id){ this.client_id = client_id }
  getDataBeamURLHTTP() { return "http://" + this.databeam_url + "/" }
  getDataBeamURLWebSocket() {return "ws://" + this.databeam_ws_url}
  getMeasurements() { return this.measurements }
  getModules() { return this.modules }
  getConfigDirty() { return this.config_dirty }
  getConfig() { return this.config }
  getConfigEntries(){ return this.config_entries }
  getConfigModuleName() { return this.config_module_name }
  getSystemMeta(){ return this.system_meta }
  getUserMeta(){ return this.user_meta }
  getDataBeamTimeNS() { return this.databeam_time_ns }
  getDataBeamTimeString() { return this.databeam_time_str }
  getBusyJobs() { return this.busy_jobs }
  getClientID() { return this.client_id }
  getPreviewData() { return this.preview_data }
  getModuleDocumentation() { return this.module_documentation }
  getSelectedModule() { return this.selected_module }
  getStateJob() { return this.state_job }
  getEventModulesChanged(){ return this.event_modules_changed }
  getEventFilesChanged(){ return this.event_files_changed }
  getEventMetaChanged(){ return this.event_meta_changed }
  getOnlineStatus(){ return this.online_status }
  getDockerContainers(){ return this.containers }
  getSelectedContainerID() { return this.selected_container_id }
  getDockerLogs(){ return this.container_log }
  getDockerInfoFlag() { return this.docker_log_filter[0] }
  getDockerWarningFlag() { return this.docker_log_filter[1] }
  getDockerDebugFlag() { return this.docker_log_filter[2] }
  getDockerErrorFlag() { return this.docker_log_filter[3] }
  getTheme() {return this.theme }
  getCaptureRunning() { return this.capture_running }
  getSamplingRunning() { return this.sampling_running }
  getRootConfigEntry(){return this.root_config_entry}
  getConfigLayout() { return this.config_layout }

  setEventModulesChanged(state) { this.event_modules_changed = state }
  setEventFilesChanged(state) { this.event_files_changed = state }
  setEventMetaChanged(state) { this.event_meta_changed = state }

  getModuleByName(name)
  {
    for(let i = 0; i < this.modules.length; i++)
    {
      if(this.modules[i].getName() == name) return this.modules[i]
    }

    return undefined
  }

  getMeasurementByName(name, measurement_list = undefined)
  {
    if(measurement_list == undefined) measurement_list = this.measurements

    for(let i = 0; i < measurement_list.length; i++)
    {
      if(measurement_list[i].getName() == name) return measurement_list[i]
    }

    return undefined
  }

  setTheme(theme)
  {
    this.theme = theme
    localStorage.setItem("theme", theme)
    this.view.onModelThemeChanged()
  }

  setOnlineStatus(online_status)
  {
    this.online_status = online_status
    this.view.onlineStatusChanged()
  }

  setSelectedModule(module_name)
  {
    this.selected_module = module_name
    this.view.onModulesChanged()
  }

  setReplyStatus(json)
  {
    if(json.status.error) 
    {
      this.view.onErrorMessage(json.status.title, json.status.message)
      return false
    }

    return true
  }

  setDockerLogsFilter(type_index, flag)
  {
    if(type_index > 3 || type_index < 0) return;
    this.docker_log_filter[type_index] = flag
    this.view.onDockerLogsChanged()
  }

  setDockerLogs(short_id, json)
  {
    console.log("Model:setContainerLog(" + short_id +  ")")
    this.selected_container_id = short_id;
    this.container_log = json.logs;
    this.container_log = this.container_log .replaceAll("<", "&lt;")
    this.container_log = this.container_log .replaceAll(">", "&gt;")
    this.view.onDockerContainersChanged()
    this.view.onDockerLogsChanged()
  }

  setDockerContainers(json)
  {
    console.log(json)

    //clear containers
    this.containers = []

    //get containers from json
    let containers = json.containers

    //get containers from json
    for(var i = 0; i < containers.length; i++)
    {
      let device = new ContainerEntry(
        containers[i].id,
        containers[i].name,
        containers[i].image,
        //json_containers[i].labels,
        containers[i].short_id,
        containers[i].status)

      this.containers.push(device)
    }

    //sort containers by name
    this.containers.sort((a, b) => a.getName() < b.getName() ? -1  : 1)

    //notify listeners
    this.view.onDockerContainersChanged()
  }

  setJobs(json)
  {
    //clear jobs
    this.jobs = []
    this.busy_jobs = []

    let state_job_changed = false
    let log_jobs = []
    let ready_state_changed = false

    //iterate received jobs
    for(let i = 0; i < json.jobs.length; i++)
    {
      if(json.jobs[i].type == "time")
      {
        this.databeam_time_ns = json.jobs[i].data.time_ns
        this.databeam_time_str = json.jobs[i].data.time_str
      }
      else if(json.jobs[i].type == "ready")
      {
        let ready_job = json.jobs[i]
        let m = this.getModuleByName(ready_job.data.module_name)

        if(m != undefined)
        {
          if(m.getReady() != ready_job.data.ready) ready_state_changed = true
          m.setReady(ready_job.data.ready)
        }
      }
      else if(json.jobs[i].type == "state")
      {
        this.state_job = json.jobs[i]
        state_job_changed = this.sampling_running != this.state_job.data.sampling || this.capture_running != this.state_job.data.capture
        this.capture_running = this.state_job.data.capture
        this.sampling_running = this.state_job.data.sampling
      }
      else if(json.jobs[i].type == "busy")
      {
        this.busy_jobs.push(new BusyJob(json.jobs[i]))
      }
      else if(json.jobs[i].type == "event")
      {
        this.setEventModulesChanged(json.jobs[i].data.modules_changed)
        this.setEventFilesChanged(json.jobs[i].data.files_changed)
        this.setEventMetaChanged(json.jobs[i].data.meta_changed)
      }
      else if(json.jobs[i].type == "log")
      {
        //console.log(json.jobs[i].data)
        log_jobs.push(json.jobs[i].data)
      }
      else
      {
        console.error("Model: Unknown Job Received.")
      }
    }

    //jobs changed, run callback
    this.view.onJobsChanged()

    if(state_job_changed) 
    {
      this.view.onStateJobChanged()
      this.view.onMeasurementsChanged()
    }

    // update modules if any ready state changed
    if(ready_state_changed) this.view.onModulesChanged()

    //update view with all received log jobs
    for(let i = 0; i < log_jobs.length; i++) this.view.onLogJob(log_jobs[i])
  }

  setPreviewData(preview_json_str)
  {
    this.preview_data = JSON.parse(preview_json_str)
    this.view.onPreviewDataChanged()
  }

  setMeasurements(measurement_json)
  {
    let measurement_list = measurement_json.measurements

    let old_measurements = this.measurements
    this.measurements = []

    for(let i = 0; i < measurement_list.length; i++)
    {
      let measurement_entry = new MeasurementEntry(measurement_list[i])
      let old_measurment_entry = this.getMeasurementByName(measurement_entry.getName(), old_measurements)

      if(old_measurment_entry != undefined)
      {
        measurement_entry.setSelected(old_measurment_entry.getSelected())
      }

      this.measurements.push(measurement_entry)
    }

    this.view.onMeasurementsChanged()
  }

  setAllMeasurementsSelected(selected)
  {
    for(let i = 0; i < this.measurements.length; i++)
    {
      this.measurements[i].setSelected(selected)
    }

    this.view.onMeasurementsChanged()
  }

  setMeasurementSelected(measurement_name, selected)
  {
    let measurement_entry = this.getMeasurementByName(measurement_name)
    if(measurement_entry != undefined) measurement_entry.setSelected(selected)
    this.view.onMeasurementsChanged()
  }

  setLatestTopic(latest_topic)
  {
    let module = this.getModuleByName(this.selected_module)
    if(module == undefined) return
    module.setLatestTopic(latest_topic)
  }

  setModules(modules_json)
  {
    //console.log(JSON.stringify(modules_json))

    let modules_list = modules_json.modules

    //store previous modules
    let prev_modules = this.modules

    //clear modules
    this.modules = []

    //create new modules list
    for(let i = 0; i < modules_list.length; i++)
    {
      let modules_entry = new ModuleEntry(modules_list[i])
      this.modules.push(modules_entry)
    }

    //restore ready states from old modules list
    for(let i = 0; i < prev_modules.length; i++)
    {
      let module_name = prev_modules[i].getName()
      let m = this.getModuleByName(module_name)

      if(m != undefined) 
      {
        m.setReady(prev_modules[i].getReady())
        m.setLatestSchemaIndex(prev_modules[i].getLatestSchemaIndex())
      }
    }

    //sort modules by name
    this.modules.sort((a, b) => {return a.getName() < b.getName() ? -1 : 1});

    //update modules table
    this.view.onModulesChanged()

    //check if config module is missing
    if(this.config_module_name != "")
    {
      if(this.getModuleByName(this.config_module_name) == undefined)
      {
        this.config_module_name = ""
        this.view.onConfigChanged()
      }
    }
  }

  setModuleDocumentation(documentation) 
  { 
    let index_start = documentation.indexOf("[Link:")
    
    if(index_start != -1)
    {
      let index_end = documentation.indexOf("]", index_start)
      let link_str = documentation.substring(index_start + 1, index_end)
      let parts = link_str.split(":")
      let search_str = "[" + link_str + "]"
      let replace_str = "<a href=\"http://" + this.databeam_ip + ":" + parts[1] + "\" target=\"_blank\">" + parts[2] + "</a>"
      documentation = documentation.replace(search_str, replace_str)
    }

    this.module_documentation = documentation 
    this.view.onDocumentationChanged()
  }

  setMeta(meta_json)
  {
    //parse system meta and store
    this.system_meta = JSON.parse(meta_json.system_meta_json)

    //parse user meta
    let user_meta_dict = JSON.parse(meta_json.user_meta_json)

    //clear user meta
    this.user_meta = []
    this.user_meta.push(new MetaEntry("", ""))

    //get keys
    let user_meta_keys = Object.keys(user_meta_dict);

    //get meta entries from json
    for(var i = 0; i < user_meta_keys.length; i++)
    {
      let key = user_meta_keys[i]
      let meta_entry = new MetaEntry(key, user_meta_dict[key])
      this.user_meta.push(meta_entry)
    }

    this.view.onMetaChanged()
  }

  toggleConfigLayout()
  {
    this.config_layout = this.config_layout == "wrap" ? "nowrap" : "wrap"
    localStorage.setItem("config_layout", this.config_layout)
    this.view.onConfigChanged()
  }

  setConfigString(module_name, config_string)
  {
    console.log("Model:setConfigString(" + module_name + ", ...)")
    this.config = config_string;
    this.config_module_name = module_name
    this.config_json = JSON.parse(this.config)
    let old_object_entries = this.getObjectConfigEntries(this.config_entries)
    this.config_entries = []
    this.root_config_entry = new ConfigEntry()
    this.walkObject(this.config_json, this.root_config_entry)
    this.restoreObjectEntryStates(old_object_entries)
    this.setConfigEntryVisibility()
    this.view.onConfigChanged()
  }

  setConfig(module_name, data, dirty)
  {
    console.log("Model:setConfig(" + module_name + ", ...)")

    this.config_dirty = dirty

    //parse device config
    let json_cfg = JSON.parse(data.json)
    let pretty_json_string = JSON.stringify(json_cfg, null, 2)
    this.config = pretty_json_string;
    this.config_json = json_cfg
    this.config_module_name = module_name

    //parse config entries
    let old_object_entries = this.getObjectConfigEntries(this.config_entries)
    this.config_entries = []
    this.root_config_entry = new ConfigEntry()
    this.walkObject(this.config_json, this.root_config_entry)
    this.restoreObjectEntryStates(old_object_entries)
    this.setConfigEntryVisibility()

    //set config
    pretty_json_string = JSON.stringify(this.config_json, null, 2)
    this.config = pretty_json_string;

    //updated config inspector and devices table
    this.view.onConfigChanged()
    //this.configInspectorChangedCB()
    //this.devicesChangedCB()
  }

  pushConfigArrayEntry(config_index)
  {
    let entry = this.config_entries[config_index]
    this.config_dirty = true
    entry.pushArray()
    this.config = JSON.stringify(this.config_json, null, 2)
    this.view.onConfigChanged()
  }

  popConfigArrayEntry(config_index)
  {
    let entry = this.config_entries[config_index]
    this.config_dirty = true
    entry.popArray()
    this.config = JSON.stringify(this.config_json, null, 2)
    this.view.onConfigChanged()
  }

  initConfigArrayType(config_index, array_type)
  {
    let entry = this.config_entries[config_index]
    entry.initArray(array_type)
    this.config = JSON.stringify(this.config_json, null, 2)
    this.view.onConfigChanged()
  }

  updateConfigEntry(config_index, array_index, value)
  {
    //get config entry
    let entry = this.config_entries[config_index]
    this.config_dirty = true

    //update array or single value
    if(array_index >= 0)
    {
      entry.updateArray(array_index, value)
    }
    else
    {
      if(entry.getType() == "object")
      {
        entry.setSubVisible(value)
      }
      else 
      {
        entry.update(value)
      }
    }

    //updated config string and config inspector
    this.config = JSON.stringify(this.config_json, null, 2)
    let old_object_entries = this.getObjectConfigEntries(this.config_entries)
    this.config_entries = []
    this.root_config_entry = new ConfigEntry()
    this.walkObject(this.config_json, this.root_config_entry)
    this.restoreObjectEntryStates(old_object_entries)
    this.setConfigEntryVisibility()
    this.view.onConfigChanged()
  }

  updateConfig(config_string, config_dirty)
  {
    console.log("Model:updateConfig()")
    this.config_dirty = config_dirty
    this.config = config_string;
    this.config_json = JSON.parse(this.config)
    let old_object_entries = this.getObjectConfigEntries(this.config_entries)
    this.config_entries = []
    this.root_config_entry = new ConfigEntry()
    this.walkObject(this.config_json, this.root_config_entry)
    this.restoreObjectEntryStates(old_object_entries)
    this.setConfigEntryVisibility()
    this.view.onConfigChanged()
  }

  getObjectConfigEntries(config_entries)
  {
    let object_entries = {}

    for(var i = 0; i < config_entries.length; i++)
    {
      let e = this.config_entries[i]

      if(e.getType() == "object") object_entries[e.getLabel()] = e
    } 

    return object_entries
  }

  restoreObjectEntryStates(old_object_entries)
  {
    let object_entries = this.getObjectConfigEntries(this.config_entries)

    for(const [key, value] of Object.entries(object_entries))
    {
      if(key in old_object_entries)
      {
        //console.log("Restore Object: " + key.toString())
        value.setSubVisible(old_object_entries[key].getSubVisible())
      }
    }
  }

  setConfigEntryVisibility()
  {
    let config_entry_dict = {}

    for(var i = 0; i < this.config_entries.length; i++)
    {
      let entry = this.config_entries[i]

      if(entry.isArray()) continue

      config_entry_dict[entry.getMember()] = entry
    }

    for(var i = 0; i < this.config_entries.length; i++)
    {
      this.config_entries[i].computeVisibility(config_entry_dict)
    }
  }

  walkObject(json, root, properties = {})
  {
    let keys = Object.keys(json);

    if(Object.keys(properties).length === 0 && json.hasOwnProperty("config_properties"))
    {
      properties = json["config_properties"]
    }

    for(var i = 0; i < keys.length; i++)
    {
      //skip properties
      if(keys[i] == "config_properties") continue;

      let obj = json[keys[i]]

      let type = ""

      if(typeof(obj) == "string")
      {
        type = "string"
        let config_entry = new ConfigEntry()
        config_entry.Set(json, keys[i], type, keys[i])
        if(keys[i] in properties) config_entry.setProperties(properties[keys[i]])

        //string or select
        if(keys[i] in properties)
        {
          let props = properties[keys[i]]

          if("display_type" in props)
          {
            if(props["display_type"] == "select")
            {
              config_entry.setDisplayType("select")
            }
          }
        }
        
        this.config_entries.push(config_entry)
        root.addEntry(config_entry, this.config_entries.length - 1)
      }
      else if(typeof(obj) == "number")
      {
        type = "number"
        let config_entry = new ConfigEntry()
        config_entry.Set(json, keys[i], type, keys[i]);
        if(keys[i] in properties) config_entry.setProperties(properties[keys[i]])
        this.config_entries.push(config_entry)
        root.addEntry(config_entry, this.config_entries.length - 1)
      }
      else if(typeof(obj) == "boolean")
      {
        type = "boolean"
        let config_entry = new ConfigEntry()
        config_entry.Set(json, keys[i], type, keys[i]);
        if(keys[i] in properties) config_entry.setProperties(properties[keys[i]])
        this.config_entries.push(config_entry)
        root.addEntry(config_entry, this.config_entries.length - 1)
      }
      else if(typeof(obj) == "object")
      {
        if(Array.isArray(obj))
        {
          type = "array"
          let config_entry = new ConfigEntry()
          config_entry.Set(obj, "array", typeof(obj[0]), keys[i]);
          if(keys[i] in properties) config_entry.setProperties(properties[keys[i]])
          this.config_entries.push(config_entry)
          root.addEntry(config_entry, this.config_entries.length - 1)
        }
        else{
          type = "object"
        }
      }
      else{
        type == "undefined"
      }

      if(type == "object")
      {
        let config_entry = new ConfigEntry();
        config_entry.Set(obj, keys[i], "object", keys[i])
        if(keys[i] in properties) config_entry.setProperties(properties[keys[i]])
        this.config_entries.push(config_entry)
        root.addEntry(config_entry, this.config_entries.length - 1)
        this.walkObject(obj, config_entry, keys[i] in properties ? properties[keys[i]]['config_properties'] : {})
      }
    }
  }
}
  