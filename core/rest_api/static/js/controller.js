class Controller 
{
  constructor(model, view)
  {
    console.log('Creating Controller.')

    //store controller and viewe references
    this.model = model
    this.view = view

    this.view.init(this, this.model)
    this.model.init(this, view)

    //connect to websocket
    console.log("Connect to: " + this.model.getDataBeamURLWebSocket())
    this.ws = new WebSocket(this.model.getDataBeamURLWebSocket());
    this.ws.addEventListener("message", event => this.onWebSocketMessage(event.data))
    this.ws.addEventListener("open", () => this.onWebSocketOpen())
    this.ws.addEventListener("close", () => this.onWebSocketClose())
    this.ws.addEventListener("error", () => this.onWebSocketError())
    this.ws_reconnect = false

    //fetch metadata
    this.fetchMeta()
  }

  onWebSocketMessage(json_str)
  {
    //console.log("WebSocket Message: " + json_str)

    let msg = JSON.parse(json_str)

    if(msg.type == "job")
    {
      this.model.setJobs(JSON.parse(msg.data))

      if(this.model.getEventModulesChanged()) 
      {
        this.model.setEventModulesChanged(false)
        this.fetchModules()
      }

      if(this.model.getEventFilesChanged()) 
      {
        this.model.setEventFilesChanged(false)
        this.fetchMeasurements()
      }

      if(this.model.getEventMetaChanged()) 
      {
        this.model.setEventMetaChanged(false)
        this.fetchMeta()
      }
    }
    else if(msg.type == "id")
    {
      console.log("WS ID: " + msg.id)
      this.model.setClientID(msg.id)
    }
    else if(msg.type == "preview")
    {
      //console.log("Preview: " + msg.data)
      this.model.setPreviewData(msg.data)
    }
    else
    {
      console.error("WS received unknown message type.")
    }
  }

  onWebSocketOpen()
  {
    console.log("WebSocket Open.")
    this.model.setOnlineStatus(true)
  }

  onWebSocketClose()
  {
    console.log("WebSocket Close.")
    this.model.setOnlineStatus(false)
  }

  onWebSocketError()
  {
    console.log("WebSocket Error.")
  }

  startSampling()
  {
    console.log("Controller:startSampling()")
    let self = this
    let json_object = {run_tag: "default"};

    fetch(this.model.getDataBeamURLHTTP() + "/start_sampling", {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(json_object),
    })
    .then(response => response.json())
    .then(data => {
      this.model.setReplyStatus(data)
    })
  }

  stopSampling()
  {
    console.log("Controller:stopSampling()")
    let self = this
    let json_object = {run_tag: "default"};

    fetch(this.model.getDataBeamURLHTTP() + "/stop_sampling", {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(json_object),
    })
    .then(response => response.json())
    .then(data => {
      this.model.setReplyStatus(data)
    })
  }

  start()
  {
    console.log("Controller:start()")
    let self = this
    let json_object = {run_tag: "default"};

    fetch(this.model.getDataBeamURLHTTP() + "/start", {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(json_object),
    })
    .then(response => response.json())
    .then(data => {
      this.model.setReplyStatus(data)
    })
  }

  stop()
  {
    console.log("Controller:stop()")
    let self = this
    let json_object = {run_tag: "default"};

    fetch(this.model.getDataBeamURLHTTP() + "/stop", {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(json_object),
    })
    .then(response => response.json())
    .then(data => {
      if(this.model.setReplyStatus(data)){
        this.fetchMeasurements()
      }
    })
  }

  fetchMeasurements()
  {
    console.log("Controller:fetchMeasurements()")
    let self = this
    let json_object = {run_tag: "default"};

    fetch(this.model.getDataBeamURLHTTP() + "/measurements")
    .then(response => response.json())
    .then(data => this.model.setMeasurements(data))
  }

  fetchDocumentation(module_name)
  {
    console.log("Controller:fetchMeasurements()")
    let self = this

    fetch(this.model.getDataBeamURLHTTP() + "/modules/documentation/" + module_name)
    .then(response => response.json())
    .then(data => {
      if(this.model.setReplyStatus(data))
      {
        self.model.setSelectedModule(module_name)
        self.model.setModuleDocumentation(data.documentation) 
      }
    })
  }

  fetchModules()
  {
    console.log("Controller:fetchModules()")

    fetch(this.model.getDataBeamURLHTTP() + "/modules")
    .then(response => response.json())
    .then(data => {
      if(this.model.setReplyStatus(data))
      {
        this.model.setModules(data)
      }
    })
  }

  fetchConfig(module_name)
  {
    console.log("Controller:fetchConig()")

    let self = this
    fetch(this.model.getDataBeamURLHTTP() + "modules/config/" + module_name)
    .then(response => response.json())
    .then(data => {
      if(this.model.setReplyStatus(data))
      {
        self.model.setConfig(module_name, data, false)
        self.model.setSelectedModule(module_name)
      }
    })
  }

  fetchID()
  {
    console.log("Controller:fetchID()")

    let self = this
    fetch(this.model.getDataBeamURLHTTP() + "id")
    .then(response => response.json())
    .then(data => {
      console.log(data)
      this.ws.send(JSON.stringify({id: data.id}))
    })
  }

  fetchDockerContainers()
  {
    console.log("Controller:fetchDockerContainers()")

    let self = this
    fetch(this.model.getDataBeamURLHTTP() + "docker/containers")
    .then(response => response.json())
    .then(data => this.model.setDockerContainers(data))
  }

  fetchDockerLogs(short_id)
  {
    console.log("Controller:fetchDockerLogs()")

    let self = this
    fetch(this.model.getDataBeamURLHTTP() + "docker/logs/" + short_id)
    .then(response => response.json())
    .then(data => {
      this.model.setDockerLogs(short_id, data)
    })
  }

  fetchMeta(module_name)
  {
    console.log("Controller:fetchMeta()")

    let self = this
    fetch(this.model.getDataBeamURLHTTP() + "meta")
    .then(response => response.json())
    .then(data => {
      if(this.model.setReplyStatus(data))
      {
        this.model.setMeta(data)
      }
    })
  }

  updateSystemMeta(new_system_meta)
  {
    console.log("Controller:updateSystemMeta()")

    let meta_json = {system_meta: new_system_meta};

    //send user meta
    let self = this
    fetch(this.model.getDataBeamURLHTTP() + "system_meta", {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(meta_json),
    })
    .then(response => response.json())
    .then(data => {
      if(this.model.setReplyStatus(data))
      {
        self.fetchMeta()
      }
    })
  }

  updateUserMeta(new_user_meta)
  {
    console.log("Controller:updateUserMeta()")

    let meta_json = {user_meta: new_user_meta};

    //send user meta
    let self = this
    fetch(this.model.getDataBeamURLHTTP() + "user_meta", {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(meta_json),
    })
    .then(response => response.json())
    .then(data => {
      if(this.model.setReplyStatus(data))
      {
        self.fetchMeta()
      }
    })
  }

  updateDataConfig(module_name, new_data_config)
  {
    //send data config
    let self = this
    fetch(this.model.getDataBeamURLHTTP() + "modules/data_config/" + module_name, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(new_data_config),
    })
    .then(response => response.json())
    .then(data => {
      if(this.model.setReplyStatus(data))
      {
        console.log("Controller:updateDataConfig for " + module_name + ": " + JSON.stringify(new_data_config))
        self.fetchModules()
      }
    })
  }

  onAppyConfig(config_str)
  {
    //get config device name
    let module_name = this.model.getConfigModuleName()

    //leave if there is no config
    if(module_name == ""){
      console.log("Warning: Get Config first before Apply.")
      return;
    }

    //update the config in the model
    this.model.updateConfig(config_str, false);

    //send config
    let self = this
    fetch(this.model.getDataBeamURLHTTP() + "modules/apply_config/" + module_name, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(JSON.parse(config_str)),
    })
    .then(response => response.json())
    .then(data => {
      self.model.setReplyStatus(data)
    })
  }

  onPostConfigButtonClick(cfg_key)
  {
    //get config device name
    let module_name = this.model.getConfigModuleName()

    //leave if there is no config
    if(module_name == ""){
      console.log("Warning: Get Config first before Apply.")
      return;
    }

    let json_object = {"cfg_key": cfg_key}

    //send config button click
    let self = this
    fetch(this.model.getDataBeamURLHTTP() + "modules/config_button/" + module_name, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(json_object),
    })
    .then(response => response.json())
    .then(data => {
      self.model.setReplyStatus(data)
    })
  }

  postSystemCommand(command)
  {
    let self = this
    let json_object = {cmd: command}

    //send data config
    fetch(this.model.getDataBeamURLHTTP() + "system_cmd", {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(json_object),
    })
    .then(response => response.json())
    .then(data => {
      self.model.setReplyStatus(data)
    })
  }

  onStoreConfig(config_str)
  {
    //get config device name
    let module_name = this.model.getConfigModuleName()

    this.model.updateConfig(config_str, this.model.getConfigDirty());
    this.downloadFile(config_str, module_name + "_config" + ".json", "text/plain")
  }

  downloadFile(content, file_name, content_type) {
    let a = document.createElement("a");
    let file = new Blob([content], { type: content_type });
    a.href = URL.createObjectURL(file);
    a.download = file_name;
    a.click();
  }

  onDownloadDockerLogs()
  {
    console.log("Controller:onDownloadDockerLogs()")

    let a = document.createElement("a");
    document.body.appendChild(a)
    a.href = this.model.getDataBeamURLHTTP() + "/download/logs";
    a.download = "logs.zip"
    a.click()
    document.body.removeChild(a)
  }

  onLoadConfigFileChanged(file)
  {
    //get config device name
    let module_name = this.model.getConfigModuleName()
    self = this

    if(module_name == "")
    {
      console.log("Warning: Get Config first before Load.")
      return;
    }

    let fileReader = new FileReader();

    fileReader.onload = (event) => {
        let text = event.target.result;
        self.model.setConfigString(module_name, text)
    };

    fileReader.readAsText(file, "UTF-8");
  }

  onDefaultConfig()
  {
    let module_name = this.model.getConfigModuleName()
    let self = this

    if(module_name == ""){
      console.log("Controller: No Config Selected.")
      return
    }

    fetch(this.model.getDataBeamURLHTTP() + "modules/default_config/" + module_name)
    .then(response => response.json())
    .then(data => {
      if(this.model.setReplyStatus(data))
      {
        self.model.setConfig(module_name, data, true)
      }
    })
  }

  downloadSelectedMeasurements()
  {
    //get data bases from model
    let measurements = this.model.getMeasurements()
    let measurement_names = []
    let capture = this.model.getCaptureRunning()

    for(let i = 0; i < measurements.length; i++) 
    {
      if(measurements[i].getSelected() == false) continue
      if(measurements[i].getDuration() != "" || !capture) measurement_names.push(measurements[i].getName())
    }

    if(measurement_names.length == 0) return

    let json = {'measurement_names': measurement_names}

    let self = this
    fetch(this.model.getDataBeamURLHTTP() + "download/batch_list", {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(json),
    })
    .then(response => response.json())
    .then(data => {
      let a = document.createElement("a");
      document.body.appendChild(a)
      a.href = this.model.getDataBeamURLHTTP() + "/download/batch/" + data.batch_id.toString();
      a.download = "measurements_" + data.batch_id.toString() + ".zip"
      a.click()
      document.body.removeChild(a)
    })
  }

  removeSelectedMeasurements()
  {
    //get data bases from model
    let measurements = this.model.getMeasurements()
    let measurement_names = []
    let capture = this.model.getCaptureRunning()

    for(let i = 0; i < measurements.length; i++) 
    {
      if(measurements[i].getSelected() == false) continue
      if(measurements[i].getDuration() != "" || !capture) measurement_names.push(measurements[i].getName())
    }

    if(measurement_names.length > 0) this.removeMeasurement(measurement_names)
  }

  removeMeasurement(measurement_names)
  {
    console.log("Controller:removeMeasurement()")
    let self = this
    let json_object = {'measurements': measurement_names};

    fetch(this.model.getDataBeamURLHTTP() + "/remove/measurements", {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(json_object),
    })
    .then(response => response.json())
    .then(data => {
      console.log(JSON.stringify(data))
      this.fetchMeasurements()
    })
  }

  requestPreview(module_name)
  {
    console.log("Controller:requestPreview()")

    let module = this.model.getModuleByName(module_name)
    let schema_index = module != undefined ? module.getLatestSchemaIndex() : 0

    let self = this

    let json_object = {
      id: this.model.getClientID(), 
      module_name: module_name,
      schema_index: schema_index
    };

    fetch(this.model.getDataBeamURLHTTP() + "/preview", {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(json_object),
    })
    .then(response => response.json())
    .then(data => {
      self.model.setSelectedModule(module_name)
    })
  }

  onTabSwitched(name)
  {
    if(name == 'modules_div_id'){
      this.fetchModules()
    }
    else if(name == 'data_div_id'){
      this.fetchMeasurements()
    }
    else if(name == 'system_div_id'){
      this.fetchDockerContainers()
      return
    }
    else{ 
      return 
    }
  }
}

var app = new Controller(new Model(), new View());
