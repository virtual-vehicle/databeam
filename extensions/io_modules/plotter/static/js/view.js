class View 
{
  constructor() 
  {
    console.log('Creating View.')

    document.getElementById('live_source_button_id').addEventListener(
      "click", event => this.onLiveSourceButtonClick(event), true);
  }

  init(controller, model)
  {
    this.controller = controller
    this.model = model
    let host_zero = window.location.hostname.length == 0
    this.model.setServerIP(host_zero ? "localhost" : window.location.hostname)

    let self = this
    document.getElementById("overlay_div_id").addEventListener('animationend', () => {
      if(self.model.getOnlineStatus())
      {
        document.getElementById("overlay_div_id").style.display = "none"
      }
    });

    this.plot_windows = []

    //for(let i = 0; i < 5; i++)
    //{
    //  this.plot_windows.push(new PlotWindow(this, document.getElementById("plot_" + i.toString() + "_div_id")))
    //}
  }

  onLiveSourceButtonClick(event)
  {
    let sidebar_div = document.getElementById("live_source_div_id")
    let shadow_div = document.getElementById("shadow_overlay_div_id")
    let show = sidebar_div.style.display == "none"
    sidebar_div.style.display = show ? "flex" : "none"
    shadow_div.style.display = show ? "flex" : "none"
  }

  createLayout(layout, modules, plot_types, plot_options, plot_channels, live_data_sources)
  {
    let main_div = document.getElementById("main_div_id")
    main_div.innerHTML = ""

    let cnt = 0

    for(let i = 0; i < layout.length; i++)
    {
      let num_cols = layout[i]

      let row_div = document.createElement("div")
      row_div.setAttribute("class", "plot-row")

      for(let c = 0; c < num_cols; c++)
      {
        let module_name = cnt < modules.length ? modules[cnt] : ""
        let plot_type = cnt < plot_types.length ? plot_types[cnt] : "Table"
        let options = cnt < plot_options.length ? JSON.parse(plot_options[cnt]) : {}
        let channels = cnt < plot_channels.length ? plot_channels[cnt] : ""
        cnt += 1
        let plot_div = document.createElement("div")
        plot_div.setAttribute("class", "plot-div")
        row_div.appendChild(plot_div)
        this.plot_windows.push(new PlotWindow(this, this.model, plot_div, module_name, plot_type, options, channels))
      }

      main_div.appendChild(row_div)
    }
  }

  onConfigChanged()
  {
    let config = this.model.getConfig()
    let layout = config['layout']
    let default_modules = config['modules']
    let default_plot_types = config['plot_types']
    let plot_options = config['options']
    let plot_channels = config['channels']
    console.log("Layout: " + JSON.stringify(layout))

    this.createLayout(layout, default_modules, default_plot_types, plot_options, plot_channels)
    this.controller.fetchModules()
  }

  onConfigUpdated()
  {
    //get current config
    let config = this.model.getConfig()
    config['options'] = []
    config['channels'] = []

    //collect requrested modules
    for(let i = 0; i < this.plot_windows.length; i++)
    {
      config['modules'][i] = this.plot_windows[i].getSelectedModule()
      config['plot_types'][i] = this.plot_windows[i].getPlotType()
      config['options'].push(this.plot_windows[i].getOptionsJsonString())
      config['channels'].push(this.plot_windows[i].getEnabledChannelsString())
    }

    config['live_data_source'] = this.model.getModulesLiveDataConfigJsonStr()

    //post new config
    this.controller.postConfig(config)
  }

  onlineStatusChanged()
  {
    let online_status = this.model.getOnlineStatus()

    console.log("Online Status changed to: " + online_status.toString())

    //get overlay div
    let overlay_div = document.getElementById("overlay_div_id")

    //fade overlay div based on websocket status
    if(online_status)
    {
      overlay_div.style.animationName = "overlay-div-fade-out-anim"
    }
    else
    {
      overlay_div.style.display = "flex"
      overlay_div.style.animationName = "overlay-div-fade-in-anim"
    }
  }

  onModulesChanged()
  {
    let modules = this.model.getModules()

    //update modules for all plots
    for(let i = 0; i < this.plot_windows.length; i++)
    {
      this.plot_windows[i].set_modules(modules)
    }

    //update live data side bar div with modules
    let live_data_div = document.getElementById("live_data_modules_div_id")
    live_data_div.innerHTML = ""

    let live_data_types = ["All", "Fixed"]

    for(let i = 0; i < modules.length; i++)
    {
      let header = document.createElement("h2")
      header.innerHTML = modules[i].getName()

      let select = document.createElement("select")
      
      for(let k = 0; k < live_data_types.length; k++)
      {
        let option = document.createElement("option");
        option.setAttribute("class", "select-option")
        option.text = live_data_types[k]
        option.selected = live_data_types[k] == modules[i].getLiveSource()
        select.add(option);
      }

      select.addEventListener("change", event => this.onModuleLiveSourceChanged(event, modules[i].getName()), true);

      let module_select_div = document.createElement("div")
      module_select_div.setAttribute("class", "live-data-row")

      module_select_div.appendChild(header)
      module_select_div.appendChild(select)
      live_data_div.appendChild(module_select_div)
    }

    this.onPlotModuleChanged()
  }

  onModuleLiveSourceChanged(event, module_name)
  {
    console.log("Live Source of module " + module_name + " changed to " + event.currentTarget.value)
    this.model.setModuleLiveSource(module_name, event.currentTarget.value)
    this.onConfigUpdated()
    this.onPlotModuleChanged()
  }

  onModuleData(module_name, data)
  {
    for(let i = 0; i < this.plot_windows.length; i++)
    {
      let p = this.plot_windows[i]
      if(module_name == p.getSelectedModule()) p.plot(data)
    }
  }

  onPlotModuleChanged()
  {
    //holds all requested modules
    let requested_modules = []
    let requested_live_sources = []

    //collect requrested modules
    for(let i = 0; i < this.plot_windows.length; i++)
    {
      let m = this.plot_windows[i].getSelectedModule()
      if(m == "") continue
      if(!requested_modules.includes(m)) requested_modules.push(m)
    }

    //create list of live sources for collected modules
    for(let i = 0; i < requested_modules.length; i++)
    {
      requested_live_sources.push(this.model.getModuleLiveSource(requested_modules[i]))
    }

    this.controller.postRequestedModules(requested_modules, requested_live_sources)
  }
}
