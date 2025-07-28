class View 
{
  constructor() 
  {
    console.log('Creating View.')

    document.getElementById('live_source_button_id').addEventListener(
      "click", event => this.onLiveSourceButtonClick(event), true);

    //holds the plot window that is currently dragged or resized
    this.drag_window = undefined

    //holds the number of rows and cols of the main div grid layout
    this.num_rows = 4
    this.num_cols = 5

    //holds the start and end cell indices of the drag window
    this.start_cell_x = 0;
    this.start_cell_y = 0;
    this.end_cell_x = 0;
    this.end_cell_y = 0;

    //true if drag window is currently resized
    this.resize_flag = false;

    //create a grid of plot indices
    this.grid = Array(this.num_rows).fill().map(() => Array(this.num_cols).fill(-1));

    //counter to assign unique ids for plot windows
    this.plot_index_count = 0

    //get main div
    this.main_div = document.getElementById("main_div_id")
  }

  init(controller, model)
  {
    //store controller and model references
    this.controller = controller
    this.model = model

    //set server ip
    let host_zero = window.location.hostname.length == 0
    this.model.setServerPort(window.location.port)
    this.model.setServerIP(host_zero ? "localhost" : window.location.hostname)
    console.log("Server: " + this.model.getServerURLHTTP())
    console.log("WS: " + this.model.getServerURLWebSocket())

    let self = this
    document.getElementById("overlay_div_id").addEventListener('animationend', () => {
      if(self.model.getOnlineStatus())
      {
        document.getElementById("overlay_div_id").style.display = "none"
      }
    });

    document.addEventListener('visibilitychange', () => {
      this.model.setTabVisible(!document.hidden)
    });

    //holds all plot windows
    this.plot_windows = []
  }

  onLiveSourceButtonClick(event)
  {
    let sidebar_div = document.getElementById("live_source_div_id")
    let shadow_div = document.getElementById("shadow_overlay_div_id")
    let show = sidebar_div.style.display == "none"
    sidebar_div.style.display = show ? "flex" : "none"
    shadow_div.style.display = show ? "flex" : "none"
  }

  createLayout(modules, plot_types, plot_options, plot_channels, grid_indices_list)
  {
    //get main div
    this.main_div.innerHTML = ""

    //register events
    this.main_div.addEventListener("mousemove", event => this.onMouseMove(event), true);
    this.main_div.addEventListener("mouseup", event => this.onMouseUp(event), true);
    this.main_div.addEventListener("dblclick", event => this.onMouseDoubleClick(event), true);
    this.main_div.addEventListener("mouseleave", event => this.onMouseLeave(event), false);

    //make sure there are stored plots
    if(grid_indices_list.length == 0) return
    if(grid_indices_list[0] === "{}") return
    
    //create stored plots
    for(let i = 0; i < grid_indices_list.length; i++)
    {
      let module_name = i < modules.length ? modules[i] : ""
      let plot_type = i < plot_types.length ? plot_types[i] : "Table"
      let options = i < plot_options.length ? JSON.parse(plot_options[i]) : {}
      let channels = i < plot_channels.length ? plot_channels[i] : ""
      let grid_indices = i < grid_indices_list.length ? JSON.parse(grid_indices_list[i])['g'] : [1, 1, 2, 2]

      this.createPlotWindow(module_name, plot_type, options, channels, grid_indices)
    }
  }

  createNewPlotWindow(grid_indices)
  {
    //create new plot window with default settings and return it
    return this.createPlotWindow("", "Table", {}, "", grid_indices)
  }

  createPlotWindow(module_name, plot_type, options, channels, grid_indices)
  {
    //create plot div
    let plot_div = document.createElement("div")
    plot_div.setAttribute("class", "plot-div")
    this.main_div.appendChild(plot_div)

    //create plot window
    let plot_window = new PlotWindow(this, this.model, plot_div, module_name, plot_type, options, channels, grid_indices, this.plot_index_count)
    this.plot_index_count += 1
    this.plot_windows.push(plot_window)

    //mark the plot window in the grid
    this.gridMark(...(grid_indices.map((n, i) => i < 2 ? n - 1 : n - 2)), plot_window.getPlotIndex())
    
    //register mouse event for header label
    plot_window.getHeaderLabel().addEventListener("mousedown", event => this.onGrabMouseDown(event, plot_window), true);
    plot_window.getHeaderLabel().setAttribute("plot_index", (this.plot_index_count-1).toString())
    
    //create resize handle
    let resize_handle = document.createElement("div")
    resize_handle.setAttribute("class", "resize-handle")
    resize_handle.innerHTML = "&#x1F53D;"
    plot_div.appendChild(resize_handle)
    resize_handle.addEventListener("mousedown", event => this.onResizeMouseDown(event, plot_window), true);
    resize_handle.setAttribute("plot_index", (this.plot_index_count-1).toString())

    //create remove handle
    let remove_handle = document.createElement("div")
    remove_handle.setAttribute("class", "remove-handle")
    remove_handle.innerHTML = "&#10060;"
    plot_div.appendChild(remove_handle)
    remove_handle.addEventListener("mousedown", event => this.onRemoveMouseDown(event, plot_window), true);
    remove_handle.setAttribute("plot_index", (this.plot_index_count-1).toString())

    //return the created plot window
    return plot_window
  }

  getPlotWindowByIndex(plot_index)
  {
    for(let i = 0; i < this.plot_windows.length; i++)
    {
      if(this.plot_windows[i].getPlotIndex() == plot_index) return this.plot_windows[i]
    }

    return undefined
  }

  gridOverlap(start_x, start_y, end_x, end_y, curr_index)
  {
    start_x = Math.max(Math.min(start_x, this.num_cols - 1), 0)
    start_y = Math.max(Math.min(start_y, this.num_rows - 1), 0)
    end_x = Math.max(Math.min(end_x, this.num_cols - 1), 0)
    end_y = Math.max(Math.min(end_y, this.num_rows - 1), 0)

    for(let x = start_x; x <= end_x; x++)
    {
      for(let y = start_y; y <= end_y; y++)
      {
        if(this.grid[y][x] != -1 && this.grid[y][x] != curr_index) return true
      }
    }

    return false
  }

  gridMark(start_x, start_y, end_x, end_y, value)
  {
    start_x = Math.max(Math.min(start_x, this.num_cols - 1), 0)
    start_y = Math.max(Math.min(start_y, this.num_rows - 1), 0)
    end_x = Math.max(Math.min(end_x, this.num_cols - 1), 0)
    end_y = Math.max(Math.min(end_y, this.num_rows - 1), 0)

    for(let x = start_x; x <= end_x; x++)
    {
      for(let y = start_y; y <= end_y; y++)
      {
        this.grid[y][x] = value
      }
    }
  }

  onResizeMouseDown(event, plot_window)
  {
    //highlight plot div
    plot_window.getPlotDiv().classList.add("highlighted")

    //set resize flag
    this.resize_flag = true

    //invoke mouse down
    this.onMouseDown(plot_window)
  }

  onRemoveMouseDown(event, plot_window)
  {
    //get index, div and grid indices for plot
    let plot_index = plot_window.getPlotIndex()
    let plot_div = plot_window.getPlotDiv()
    let grid_indices = plot_window.getGridIndices()

    //unmark div
    this.gridMark(...(grid_indices.map((n, i) => i < 2 ? n - 1 : n - 2)), -1)

    //remove plot div
    this.main_div.removeChild(plot_div)

    //remove plot window
    this.plot_windows = this.plot_windows.filter(p => p.getPlotIndex() != plot_index)

    //update config
    this.onConfigUpdated();
  }

  onGrabMouseDown(event, plot_window)
  {
    //highlight plot div
    plot_window.getPlotDiv().classList.add("highlighted")

    //invoke mouse down
    this.onMouseDown(plot_window)
  }

  onMouseDown(plot_window)
  {
    //set drag window
    this.drag_window = plot_window

    //get plot div and index
    let plot_div = plot_window.getPlotDiv()
    let plot_div_rect = plot_div.getBoundingClientRect()

    //get main div rect
    let rect = this.main_div.getBoundingClientRect()

    //compute width and height of grid cells
    let cell_w = rect.width / this.num_cols
    let cell_h = rect.height / this.num_rows

    //cumpute start cell index
    let x = plot_div_rect.left + cell_w * 0.5
    let y = plot_div_rect.top + cell_h * 0.5
    this.start_cell_x = Math.floor(x / cell_w)
    this.start_cell_y = Math.floor(y / cell_h)

    //cumpute end cell index
    x = plot_div_rect.right - cell_w * 0.5
    y = plot_div_rect.bottom - cell_h * 0.5
    this.end_cell_x = Math.floor(x / cell_w)
    this.end_cell_y = Math.floor(y / cell_h)
  }

  onMouseMove(event)
  {
    //make sure there is a drag window
    if(this.drag_window == undefined) return

    //get rect of main div
    let rect = this.main_div.getBoundingClientRect()

    //compute curser position in main div
    let x = event.clientX - rect.left
    let y = event.clientY - rect.top

    //compute width and height of grid cells
    let cell_w = rect.width / this.num_cols
    let cell_h = rect.height / this.num_rows

    //compute curser cell index
    let cell_x = Math.floor(x / cell_w)
    let cell_y = Math.floor(y / cell_h)

    //get plot div and index
    let plot_div = this.drag_window.getPlotDiv()
    let plot_index = this.drag_window.getPlotIndex()

    if(!this.resize_flag)
    {
      //check if new cell is free
      if(!this.gridOverlap(cell_x, cell_y, cell_x, cell_y, plot_index))
      {
        plot_div.style.gridColumn = `${cell_x + 1}/${cell_x + 2}`
        plot_div.style.gridRow = `${cell_y + 1}/${cell_y + 2}`
      }
    }
    else
    {
      //allow resize only in right or bottom directions
      if(cell_x <= this.start_cell_x) cell_x = this.start_cell_x;
      if(cell_y <= this.start_cell_y) cell_y = this.start_cell_y;

      //check if cells are free
      if(!this.gridOverlap(this.start_cell_x, this.start_cell_y, cell_x, cell_y, plot_index))
      {
        plot_div.style.gridColumn = `${this.start_cell_x + 1}/${cell_x + 2}`
        plot_div.style.gridRow = `${this.start_cell_y + 1}/${cell_y + 2}`
      }
    }
  }

  onMouseDoubleClick(event)
  {
    //make sure there is no dragging or resizing in progress
    if(this.drag_window != undefined) return

    //get main div rect
    let rect = this.main_div.getBoundingClientRect()

    //compute curser position in main div
    let x = event.clientX - rect.left
    let y = event.clientY - rect.top

    //compute width and height of grid cells
    let cell_w = rect.width / this.num_cols
    let cell_h = rect.height / this.num_rows

    //compute curser cell index
    let cell_x = Math.floor(x / cell_w)
    let cell_y = Math.floor(y / cell_h)

    if(!this.gridOverlap(cell_x, cell_y, cell_x, cell_y, -1))
    {
      //create a new plot window with default settings
      let plot_window = this.createNewPlotWindow([cell_x + 1, cell_y + 1, cell_x + 2, cell_y + 2]);

      //mark the plot in the grid
      this.gridMark(cell_x, cell_y, cell_x, cell_y, plot_window.getPlotIndex());

      //set the modules list for the new plot window
      plot_window.set_modules(this.model.getModules())

      //update config
      this.onConfigUpdated();
    }

    return
  }

  onMouseLeave(event)
  {
    //leave if there is no dragging or resizing in progress
    if(this.drag_window == undefined) return

    //restore grid position that was changed during move
    this.drag_window.setGridIndices(...this.drag_window.getGridIndices())

    //get plot div
    let plot_div = this.drag_window.getPlotDiv()

    //remove highlight from div and reset drag window and resize flag
    plot_div.classList.remove("highlighted")
    this.drag_window = undefined
    this.resize_flag = false
  }

  onMouseUp(event)
  {
    //make sure dragging or resizing is currently in progress
    if(this.drag_window == undefined) return

    //get main div rect
    let rect = this.main_div.getBoundingClientRect()

    //compute curser position in main div
    let x = event.clientX - rect.left
    let y = event.clientY - rect.top

    //compute width and height of grid cells
    let cell_w = rect.width / this.num_cols
    let cell_h = rect.height / this.num_rows

    //compute curser cell index
    let cell_x = Math.floor(x / cell_w)
    let cell_y = Math.floor(y / cell_h)

    //restore grid position that was changed during move
    this.drag_window.setGridIndices(...this.drag_window.getGridIndices())

    //get plot div and index
    let plot_div = this.drag_window.getPlotDiv()
    let plot_index = this.drag_window.getPlotIndex()

    if(!this.resize_flag)
    {
      //check if new cell is free
      if(!this.gridOverlap(cell_x, cell_y, cell_x, cell_y, plot_index))
      {
        //unmark old cells
        this.gridMark(this.start_cell_x, this.start_cell_y, this.end_cell_x, this.end_cell_y, -1)

        //mark new cell
        this.gridMark(cell_x, cell_y, cell_x, cell_y, plot_index)

        //set grid indices
        this.drag_window.setGridIndices(cell_x + 1, cell_y + 1, cell_x + 2, cell_y + 2)

        //update config
        this.onConfigUpdated();
      }
    }
    else
    {
      //allow resize only in right or bottom directions
      if(cell_x <= this.start_cell_x) cell_x = this.start_cell_x;
      if(cell_y <= this.start_cell_y) cell_y = this.start_cell_y;

      //check if cells are free
      if(!this.gridOverlap(this.start_cell_x, this.start_cell_y, cell_x, cell_y, plot_index))
      {
        //unmark old cells
        this.gridMark(this.start_cell_x, this.start_cell_y, this.end_cell_x, this.end_cell_y, -1)

        //mark new cells
        this.gridMark(this.start_cell_x, this.start_cell_y, cell_x, cell_y, plot_index)

        //set grid indices
        this.drag_window.setGridIndices(this.start_cell_x + 1, this.start_cell_y + 1, cell_x + 2, cell_y + 2)

        //update config
        this.onConfigUpdated();
      }
    }

    //remove highlight from div and reset drag window and resize flag
    plot_div.classList.remove("highlighted")
    this.drag_window = undefined
    this.resize_flag = false
  }

  onConfigChanged()
  {
    let config = this.model.getConfig()
    //let layout = config['layout']
    let default_modules = config['modules']
    let default_plot_types = config['plot_types']
    let plot_options = config['options']
    let plot_channels = config['channels']
    let grid_indices = config['grid_indices']
    //console.log("Layout: " + JSON.stringify(layout))

    this.createLayout(default_modules, default_plot_types, plot_options, plot_channels, grid_indices)
    this.controller.fetchModules()
  }

  onConfigUpdated()
  {
    //get current config
    let config = this.model.getConfig()
    config['options'] = []
    config['channels'] = []
    config['grid_indices'] = []

    //collect requrested modules
    for(let i = 0; i < this.plot_windows.length; i++)
    {
      config['modules'][i] = this.plot_windows[i].getSelectedModule()
      config['plot_types'][i] = this.plot_windows[i].getPlotType()
      config['options'].push(this.plot_windows[i].getOptionsJsonString())
      config['channels'].push(this.plot_windows[i].getEnabledChannelsString())
      config['grid_indices'].push(JSON.stringify({'g': this.plot_windows[i].getGridIndices()}))
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

    let module_name_list = []

    // create live data source select fields
    for(let i = 0; i < modules.length; i++)
    {
      if(modules[i].isVideoStream()) continue;

      if(module_name_list.includes(modules[i].getModuleName())) continue;
      module_name_list.push(modules[i].getModuleName())

      //create header
      let header = document.createElement("h2")
      header.innerHTML = modules[i].getModuleName()

      //create select
      let select = document.createElement("select")
      
      //create options
      for(let k = 0; k < live_data_types.length; k++)
      {
        let option = document.createElement("option");
        option.setAttribute("class", "select-option")
        option.text = live_data_types[k]
        option.selected = live_data_types[k] == modules[i].getLiveSource()
        select.add(option);
      }

      // register select change callback
      select.addEventListener("change", event => this.onModuleLiveSourceChanged(event, modules[i].getModuleName()), true);

      //create div row and append
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

      let module = this.model.getModuleByName(m)

      if(module.isVideoStream()) continue

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
