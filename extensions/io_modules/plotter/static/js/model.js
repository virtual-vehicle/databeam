class Model {
  constructor() 
  {
    console.log("Creating Model")
    this.server_ip = "localhost"
    this.server_port = "6010"
    this.ws_port = "6011"
    this.server_url = "localhost:6001"
    this.server_ws_url = "localhost:6002"
    this.client_id = -1
    this.module_data = {}
    this.modules = []
    this.config = {}
  }

  init(view)
  {
    this.view = view
  }

  setServerPort(port)
  {
    this.server_port = port
    this.ws_port = (parseInt(port) + 1).toString()
  }

  setServerIP(server_ip)
  { 
    this.server_ip = server_ip 
    this.server_url = server_ip + ":" + this.server_port
    this.server_ws_url = server_ip + ":" + this.ws_port
  }

  setClientID(client_id){ this.client_id = client_id }
  getServerURLHTTP() { return "http://" + this.server_url + "/" }
  getServerURLWebSocket() {return "ws://" + this.server_ws_url}
  getClientID() { return this.client_id }
  getOnlineStatus(){ return this.online_status }
  getModuleData() { return this.module_data }
  getModules() { return this.modules }
  getConfig() { return this.config }

  setOnlineStatus(online_status)
  {
    this.online_status = online_status
    this.view.onlineStatusChanged()
  }

  getModuleMeta(module_name)
  {
    for(let i = 0; i < this.modules.length; i++)
    {
      if(this.modules[i].getName() == module_name)
      {
        return this.modules[i].getMeta()
      }
    }

    return {}
  }

  setModuleLiveSource(module_name, live_source)
  {
    for(let i = 0; i < this.modules.length; i++)
    {
      if(this.modules[i].getName() == module_name)
      {
        this.modules[i].setLiveSource(live_source)
      }
    }
  }

  getModuleLiveSource(module_name)
  {
    for(let i = 0; i < this.modules.length; i++)
    {
      if(this.modules[i].getName() == module_name)
      {
        return this.modules[i].getLiveSource()
      }
    }

    return {}
  }

  getModulesLiveDataConfigJsonStr()
  {
    let live_dict = {}

    for(let i = 0; i < this.modules.length; i++)
    {
      live_dict[this.modules[i].getName()] = this.modules[i].getLiveSource()
    }

    return JSON.stringify(live_dict)
  }

  setModules(data)
  {
    console.log(data)

    let module_names = data['modules']
    let meta_dict = data['meta']
    let config_live_dict = JSON.parse(this.config['live_data_source'])

    for(let i = 0; i < module_names.length; i++)
    {
      let live_source = module_names[i] in config_live_dict ? config_live_dict[module_names[i]] : "Fixed"
      let module_entry = new ModuleEntry(module_names[i], meta_dict[module_names[i]], live_source)
      this.modules.push(module_entry)
    }

    //sort modules by name
    this.modules.sort((a, b) => a.getName() < b.getName() ? -1  : 1)

    this.view.onModulesChanged()
  }

  setConfig(data)
  {
    this.config = data['config']
    this.view.onConfigChanged()
  }

  setModuleData(module_name, data)
  {
    //console.log("Received " + module_name + " data")
    //this.module_data[module_name] = JSON.parse(data)
    this.view.onModuleData(module_name, JSON.parse(data))
  }
}
  