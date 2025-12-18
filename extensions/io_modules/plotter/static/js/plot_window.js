
class PlotWindow
{
  constructor(view, model, parent_div, default_module, default_plot_type, plot_options, channels, grid_indices, plot_index)
  {
    this.plot_index = plot_index
    this.grid_indices = grid_indices

    //store view
    this.view = view
    this.model = model

    //holds requested module data
    this.selected_module = default_module

    //store parent
    this.parent_div = parent_div

    //clear parent
    this.parent_div.innerHTML = ""
    this.setGridIndices(...grid_indices)

    //create header div
    this.header_div = document.createElement("div");
    this.header_div.setAttribute("class", "plot-header-div")

    //create header label
    this.header_label = document.createElement("h1")
    this.header_label.innerHTML = "Module Name"
    this.header_label.style.cursor = "move"
    this.header_div.appendChild(this.header_label)

    //div for header options
    this.header_options_div = document.createElement("div")
    this.header_options_div.setAttribute("class", "header-options-div")
    this.header_div.appendChild(this.header_options_div)

    //create plot type select
    this.plot_select = document.createElement("select")
    this.plot_types = ["Table", "Line", "Image", "Spectrum", "Oscilloscope", "Map", "Video Stream"]

    for(let i = 0; i < this.plot_types.length; i++)
    {
      let option = document.createElement("option");
      option.setAttribute("class", "select-option")
      option.text = this.plot_types[i]
      option.selected = this.plot_types[i] == default_plot_type
      this.plot_select.add(option);
    }

    this.plot_select.addEventListener("change", event => this.onPlotTypeChanged(event), true);
    this.header_options_div.appendChild(this.plot_select)

    //create modules select
    this.modules_select = document.createElement("select")
    this.modules_select.addEventListener("change", event => this.onModuleSelectionChanged(event), true);
    this.header_options_div.appendChild(this.modules_select)

    //create button to toggle plot options
    this.options_button = document.createElement("div")
    this.options_button.innerHTML = "&#128295;" // "&#128200;"
    this.options_button.setAttribute("class", "emoji-button")
    this.options_button.addEventListener("click", event => this.onOptionsButtonClick(event));
    this.header_options_div.appendChild(this.options_button)

    //create options div
    this.options_div = document.createElement("div")
    this.options_div.setAttribute("class", "plot-options-div")
    this.options_div.style.display = "none"

    //create enabled channels header
    this.enabled_ch_label = document.createElement("h2")
    this.enabled_ch_label.innerHTML = "Enabled Channels"
    this.options_div.appendChild(this.enabled_ch_label)

    //create div for enabled channels flags
    this.enabled_ch_buttons_div = document.createElement("div")
    this.enabled_ch_buttons_div.innerHTML = ""
    this.enabled_ch_buttons_div.setAttribute("class", "enabled-ch-div")
    this.options_div.appendChild(this.enabled_ch_buttons_div)

    //create button to toggle plot options
    this.enable_all_channels_button = document.createElement("div")
    this.enable_all_channels_button.innerHTML = "Enable All"
    this.enable_all_channels_button.setAttribute("class", "control-buttons")
    this.enable_all_channels_button.addEventListener("click", event => this.onEnableAllChannelsButtonClick(event));
    this.enabled_ch_buttons_div.appendChild(this.enable_all_channels_button)

    //create button to toggle plot options
    this.disable_all_channels_button = document.createElement("div")
    this.disable_all_channels_button.innerHTML = "Disable All"
    this.disable_all_channels_button.setAttribute("class", "control-buttons")
    this.disable_all_channels_button.addEventListener("click", event => this.onDisableAllChannelsButtonClick(event));
    this.enabled_ch_buttons_div.appendChild(this.disable_all_channels_button)

    //create div for enabled channels flags
    this.enabled_ch_div = document.createElement("div")
    this.enabled_ch_div.innerHTML = "Enabled Channels"
    this.enabled_ch_div.setAttribute("class", "enabled-ch-div")
    this.options_div.appendChild(this.enabled_ch_div)

    //create enabled channels header
    this.plot_options_label = document.createElement("h2")
    this.plot_options_label.innerHTML = "Plot Settings"
    this.options_div.appendChild(this.plot_options_label)

    //create options div for plot
    this.plot_options_div = document.createElement("div")
    this.plot_options_div.innerHTML = "This plot type does not provide any options."
    this.options_div.appendChild(this.plot_options_div)

    //create plot div
    this.plot_div = document.createElement("div")
    this.plot_div.setAttribute("class", "table-div")

    //create plot div
    this.legend_div = document.createElement("div")
    this.legend_div.setAttribute("class", "plot-legend-div")

    //append to parent
    this.parent_div.appendChild(this.header_div)
    this.parent_div.appendChild(this.plot_div)
    this.parent_div.appendChild(this.legend_div)
    this.parent_div.appendChild(this.options_div)

    //create default plot type
    if(default_plot_type == "Table") this.current_plot = new TablePlot(this.plot_div, this.legend_div, this.options_div, plot_options)
    if(default_plot_type == "Line") this.current_plot = new LinePlot(this.plot_div, this.legend_div, this.options_div, plot_options)
    if(default_plot_type == "Image") this.current_plot = new ImagePlot(this.plot_div, this.legend_div, this.options_div, plot_options)
    if(default_plot_type == "Spectrum") this.current_plot = new SpectrumPlot(this.plot_div, this.legend_div, this.options_div, plot_options)
    if(default_plot_type == "Oscilloscope") this.current_plot = new OscilloscopePlot(this.plot_div, this.legend_div, this.options_div, plot_options)
    if(default_plot_type == "Map") this.current_plot = new MapPlot(this.plot_div, this.legend_div, this.options_div, plot_options)
    if(default_plot_type == "Video Stream") this.current_plot = new VideoStreamPlot(this.plot_div, this.legend_div, this.options_div, plot_options)
    this.createOptions()
    this.current_plot.bindOptionsChangedCB(() => this.onPlotOptionsChanged())

    //store plot type
    this.plot_type = default_plot_type

    //create resize observer
    new ResizeObserver(this.plot_resized.bind(this)).observe(this.plot_div)

    //resize plot
    this.plot_resized()

    //console.log("NUM CH: " + channels.split(",").length.toString())

    this.options_enabled = false;

    this.enabled_channels = channels != "" ? channels.split(",") : []
    this.all_channels = []
  }

  setGridIndices(start_x, start_y, end_x, end_y)
  {
    this.grid_indices[0] = start_x
    this.grid_indices[1] = start_y
    this.grid_indices[2] = end_x
    this.grid_indices[3] = end_y
    this.parent_div.style.gridColumn = `${start_x}/${end_x}`
    this.parent_div.style.gridRow = `${start_y}/${end_y}`
  }

  getGridIndices()
  {
    return this.grid_indices
  }

  getPlotIndex()
  {
    return this.plot_index
  }

  getPlotDiv()
  {
    return this.parent_div
  }

  getHeaderLabel()
  {
    return this.header_label
  }

  createOptions()
  {
    //this.enabled_ch_div.innerHTML = ""
    this.current_plot.createOptions(this.plot_options_div)
  }

  addOption(parent_div, header_str, form)
  {
    let header = document.createElement("h3")
    header.innerHTML = header_str

    let div = document.createElement("div")
    div.setAttribute("class", "option-row");
    div.appendChild(header)
    div.appendChild(form)
    parent_div.appendChild(div)
  }

  updateEnabledChannelsOptions()
  {
    console.log("Update Enabled Options")

    this.enabled_ch_div.innerHTML = ""

    for(let i = 0; i < this.all_channels.length; i++)
    {
      let ch = this.all_channels[i]
      let enabled = this.enabled_channels.includes(ch)

      this.addOption(this.enabled_ch_div, ch, 
        Utils.createCheckBox([['ch', ch]], enabled, event => this.onChannelCheckBox(event)))
    }
  }

  onChannelCheckBox(event)
  {
    let ch = event.currentTarget.getAttribute("ch")
    let enabled = event.currentTarget.checked
    console.log("Channel Checkbox: " + ch)

    let enabled_ch = []

    //remove if not checked
    if(!enabled && this.enabled_channels.includes(ch))
    {
      this.enabled_channels = this.enabled_channels.filter(e => e != ch)
    }

    if(enabled && !this.enabled_channels.includes(ch))
    {
      this.enabled_channels.push(ch)
    }

    console.log("Enabled: " + this.enabled_channels.toString())

    //update config
    this.view.onConfigUpdated()
  }

  onEnableAllChannelsButtonClick(event)
  {
    this.enabled_channels = [...this.all_channels]
    this.updateEnabledChannelsOptions();
  }

  onDisableAllChannelsButtonClick(event)
  {
    this.enabled_channels = []
    this.updateEnabledChannelsOptions();
  }

  onPlotOptionsChanged()
  {
    console.log("Plot options changed cb")
    this.view.onConfigUpdated()
  }

  onOptionsButtonClick(event)
  {
    console.log("Open Plot Options")
    this.options_enabled = !this.options_enabled
    this.plot_div.style.display = this.options_enabled ? "none": "flex"
    this.legend_div.style.display = this.options_enabled ? "none": "flex"
    this.options_div.style.display = this.options_enabled ? "flex": "none"

    event.currentTarget.innerHTML = this.options_enabled ? "&#128200;" : "&#128295;"

    //update config if options window is closed
    if(!this.options_enabled) this.view.onConfigUpdated()
  }

  onPlotTypeChanged(event)
  {
    //get selected plot type
    this.plot_type = event.currentTarget.value

    //clear current plot
    this.current_plot = null
    this.plot_div.innerHTML = ""
    this.legend_div.innerHTML = ""

    //create plot
    if(this.plot_type == "Table") this.current_plot = new TablePlot(this.plot_div, this.legend_div, this.options_div, {})
    if(this.plot_type == "Line") this.current_plot = new LinePlot(this.plot_div, this.legend_div, this.options_div, {})
    if(this.plot_type == "Image") this.current_plot = new ImagePlot(this.plot_div, this.legend_div, this.options_div, {})
    if(this.plot_type == "Spectrum") this.current_plot = new SpectrumPlot(this.plot_div, this.legend_div, this.options_div, {})
    if(this.plot_type == "Oscilloscope") this.current_plot = new OscilloscopePlot(this.plot_div, this.legend_div, this.options_div, {})
    if(this.plot_type == "Map") this.current_plot = new MapPlot(this.plot_div, this.legend_div, this.options_div, {})
    if(this.plot_type == "Video Stream") this.current_plot = new VideoStreamPlot(this.plot_div, this.legend_div, this.options_div, {})
    this.current_plot.set_module_meta(this.model.getModuleMeta(this.selected_module))
    this.createOptions()
    this.current_plot.bindOptionsChangedCB(() => this.onPlotOptionsChanged())

    //resize plot
    this.plot_resized()

    //update config
    this.view.onConfigUpdated()

    //update plot for constant data (such as video stream url)
    this.plot_constant_data()
  }

  //create resize observer for plot
  plot_resized() 
  {
    let w = this.plot_div.offsetWidth
    let h = this.plot_div.offsetHeight

    if(w > 1 && h > 1) 
    {
      this.current_plot.resize(w, h)
      //console.log("Resized Plot: " + w.toString() + " x " + h.toString())
    }
    
  }

  getSelectedModule()
  {
    return this.selected_module
  }

  getPlotType()
  {
    return this.plot_type
  }

  getOptionsJsonString()
  {
    return this.current_plot.getOptionsJsonString()
  }

  getEnabledChannelsString()
  {
    return this.enabled_channels.join()
  }

  plot(data)
  {
    if(this.options_enabled) return;

    // console.log("Plot: " + JSON.stringify(data))
    if(data.hasOwnProperty("format"))
    {
      let format = data['format']

      if(format === "spectrum")
      {
        this.current_plot.plot_spectrum(data['intensity'], data['absorbance'])
      }
      else if (format === "jpeg")
      {
        this.current_plot.plot_image(data['data'], data['res_x'], data['res_y'])
      }
      else
      {
        console.log('unknown plot format in live-data: ' + format)
      }
      return
    }
    // handle gnss data in map plot, offer data to line and table too
    if("plot_map" in this.current_plot && data.hasOwnProperty("lat") && data.hasOwnProperty("lon"))
    {
      this.current_plot.plot_map(data['lat'], data['lon'])
    }

    //holds list of keys and values
    let keys = []
    let values = []
    let data_list = []

    let init_all = this.all_channels.length == 0
    let init_enabled = this.enabled_channels.length == 0

    //create list of keys and values
    for(const [key, value] of Object.entries(data))
    {
      if(key != "ts")
      {
        if(init_all) this.all_channels.push(key)
        if(init_enabled) this.enabled_channels.push(key)

        //skip disabled channels
        if(!this.enabled_channels.includes(key)) continue
      }

      data_list.push([key, value])
    }

    if(init_all || init_enabled) 
    {
      this.enabled_channels = this.enabled_channels.filter(e => this.all_channels.includes(e))
      this.updateEnabledChannelsOptions()
    }

    //sort by keys, ts is always first
    data_list.sort((a, b) => a[0] == "ts" ? -1 : (a[0] < b[0] ? -1 : 1))

    //create list of keys and values
    for(let i = 0; i < data_list.length; i++)
    {
      keys.push(data_list[i][0])
      values.push(data_list[i][1])
    }

    this.current_plot.plot(keys, values, init_all)
  }

  set_modules(modules)
  {
    this.modules_select.innerHTML = ""
    let selected_found = false

    for(let i = 0; i < modules.length; i++)
    {
      let option = document.createElement("option");
      option.setAttribute("class", "select-option")
      option.text = modules[i].getName()

      //if no module is selected use last module as default
      if(modules[i].getName() == this.selected_module || (i == modules.length - 1 && selected_found == false)) 
      {
        option.selected = true
        selected_found = true
        this.selected_module = modules[i].getName()
      }

      this.modules_select.add(option);
    }

    if(!selected_found)
    {
      this.selected_module = ""
      this.current_plot.set_module_meta({})
      this.header_label.innerHTML = "No Module Selected"
    }
    else
    {
      this.current_plot.set_module_meta(this.model.getModuleMeta(this.selected_module))
      this.header_label.innerHTML = this.selected_module
    }

    //update plot options
    this.createOptions()

    //update plot for constant data (such as video stream url)
    this.plot_constant_data()
  }

  onModuleSelectionChanged(event)
  {
    //get selected module
    this.selected_module = event.currentTarget.value

    //update header label
    this.header_label.innerHTML = this.selected_module

    //data changed, clear all and enabled channels
    this.enabled_ch_div.innerHTML = ""
    this.enabled_channels = []
    this.all_channels = []

    //update plot meta
    this.current_plot.set_module_meta(this.model.getModuleMeta(this.selected_module))

    //update plot options
    this.createOptions()

    //update module data
    this.view.onPlotModuleChanged()

    //update config
    this.view.onConfigUpdated()

    //update plot for constant data (such as video stream url)
    this.plot_constant_data()
  }

  plot_constant_data()
  {
    if(this.selected_module == "") return

    //get module
    let module = this.model.getModuleByName(this.selected_module)

    //set video stream url
    if(module != undefined)
    {
      if(module.isVideoStream()) 
      {
        this.current_plot.plot_video_stream(module.getVideoStreamURL())
      }
      else
      {
        this.current_plot.plot_video_stream("")
      }
    }
  }

  reset()
  {
    this.current_plot.reset()
  }
}