class Controller 
{
  constructor(model, view)
  {
    console.log('Creating Controller.')

    //store controller and view references
    this.model = model
    this.view = view

    //init view and model
    this.view.init(this, this.model)
    this.model.init(view)

    //set offline, update view
    //this.model.setOnlineStatus(false)

    //connect to websocket
    console.log("Connect to: " + this.model.getServerURLWebSocket())
    this.ws = new WebSocket(this.model.getServerURLWebSocket());
    this.ws.addEventListener("message", event => this.onWebSocketMessage(event.data))
    this.ws.addEventListener("open", () => this.onWebSocketOpen())
    this.ws.addEventListener("close", () => this.onWebSocketClose())
    this.ws.addEventListener("error", () => this.onWebSocketError())
    this.ws_reconnect = false

    //fetch initial state
    this.fetchConfig()
  }

  onWebSocketMessage(json_str)
  {
    let msg = JSON.parse(json_str)
    let tokens = msg.type.split("/")

    if(msg.type == "id")
    {
      console.log("WS ID: " + msg.id)
      this.model.setClientID(msg.id)
    }
    else if(msg.type == "monitor")
    {
      this.model.setMixerValues(msg.data)
    }
    else if(tokens.length == 2 && tokens[0] == "data")
    {
      this.model.setModuleData(tokens[1], msg.data)
    }
    else if(tokens.length == 3 && tokens[0] == "data")
    {
      this.model.setModuleData(tokens[1] + "/" + tokens[2], msg.data)
    }
    else
    {
      console.error("WS received unknown message type: " + msg.type)
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

  fetchModules()
  {
    console.log("Controller:fetchModules()")

    fetch(this.model.getServerURLHTTP() + "modules")
    .then(response => response.json())
    .then(data => this.model.setModules(data))
  }

  fetchConfig()
  {
    console.log("Controller:fetchConfig()")

    fetch(this.model.getServerURLHTTP() + "config")
    .then(response => response.json())
    .then(data => this.model.setConfig(data))
  }

  postConfig(new_config)
  {
    let json_data = {'config': new_config}

    //send user meta
    let self = this
    fetch(this.model.getServerURLHTTP() + "set_config", {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(json_data),
    })
    .then(response => response.json())
    .then(data => {
      console.log("Config Updated")
    })
  }

  postRequestedModules(requested_modules, requested_live_sources)
  {
    let json_data = {
      "modules": requested_modules,
      "live_sources": requested_live_sources
    }

    //send user meta
    let self = this
    fetch(this.model.getServerURLHTTP() + "requested_modules", {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(json_data),
    })
    .then(response => response.json())
    .then(data => {
      console.log("Requested Modules")
    })
  }
}

var app = new Controller(new Model(), new View());
