
class LinePlot extends Plot
{
  constructor(plot_div, legend_div, options_div, plot_options)
  {
    //call base constructor
    super();

    //store parameters
    this.plot_div = plot_div
    this.legend_div = legend_div
    this.options_div = options_div

    //define colors array
    // https://www.heavy.ai/blog/12-color-palettes-for-telling-better-stories-with-your-data
    this.line_colors = [
      "#e60049",
      "#0bb4ff",
      "#50e991",
      "#e6d800",
      "#9b19f5",
      "#ffa300",
      "#dc0ab4",
      "#b3d4ff",
      "#00bfa0"
    ]
    
    //read config parameters
    this.num_samples = plot_options.hasOwnProperty("n") ? plot_options["n"] : 200
    this.time_range = plot_options.hasOwnProperty("time_range") ? Math.abs(plot_options["time_range"]) : 5
    this.update_frequency = plot_options.hasOwnProperty("f") ? Math.abs(plot_options["f"]) : 30
    this.update_period = 1 / this.update_frequency

    let self = this

    //define opts for plot
    this.opts = {
      title: "",
      width: 500,
      height: 500,
      pxAlign: false,
      scales: {
        x: {
          time: false,
          auto: true,
          range: (self_p, tmin, tmax) => {
            return [-self.time_range, 0.0]
          }
        },
        y: {
        	auto: true,
          //range: (self, dataMin, dataMax) => uPlot.rangeNum(dataMin, dataMax, 0.5, true)
        }
      },
      axes: [
        {
          space: 50,
        },
        {
          size(self, values, axisIdx, cycleNum) {
            let axis = self.axes[axisIdx];

            // bail out, force convergence
            if (cycleNum > 1)
              return axis._size;

            let axisSize = axis.ticks.size + axis.gap;

            // find longest value
            let longestVal = (values ?? []).reduce((acc, val) => (
              val.length > acc.length ? val : acc
            ), "");

            if (longestVal != "") {
              self.ctx.font = axis.font[0];
              axisSize += self.ctx.measureText(longestVal).width / devicePixelRatio;
            }

            return Math.ceil(axisSize);
          },
        }
      ],
      series: [
        {},
      ],
      legend: {
        show: false
      }
    };

    //holds data
    this.data = []

    //holds data time stamps in ns
    this.ts = []

    //holds number of lines in plot
    this.num_lines = 0

    //holds the line plot instance
    this.line_plot = new uPlot(this.opts, this.data, this.plot_div);
    
    //holds all incoming channel names
    this.all_channels = []

    //holds the last animation timestamp
    this.last_animation_ts = -1

    //holds the delta time since the last animation update
    this.dt_accum = 0.0

    this.frame_cnt = 0

    this.last_ts = 0

    this.t_correction = 0

    //start animation update loop
    window.requestAnimationFrame(this.animationUpdate.bind(this))
  }

  addOption(header_str, form)
  {
    let header = document.createElement("h3")
    header.innerHTML = header_str

    let div = document.createElement("div")
    div.setAttribute("class", "option-row");
    div.appendChild(header)
    div.appendChild(form)
    this.options_div.appendChild(div)
  }

  createOptions(div)
  {
    //clear options div
    //this.options_div.innerHTML = ""
    console.log("Update Plot Options")

    //number of samples
    this.options_div = div
    this.options_div.innerHTML = ""
    this.addOption("Max Samples", Utils.createNumberInput(this.num_samples, event => this.onNumSamplesChanged(event)))
    this.addOption("Max Time [s]", Utils.createNumberInput(this.time_range, event => this.onMinXChanged(event)))
    this.addOption("Refresh Rate [Hz]", Utils.createNumberInput(this.update_frequency, event => this.onFrequencyChanged(event)))
  }

  onNumSamplesChanged(event)
  {
    let n = parseFloat(event.currentTarget.value)
    this.num_samples = Math.min(Math.max(10, n), 2048)
    event.currentTarget.value = this.num_samples
    this.optionsChangedCB()
  }

  onMinXChanged(event)
  {
    let t = Math.abs(parseFloat(event.currentTarget.value))
    this.time_range = Math.min(Math.max(2, t), 120)
    event.currentTarget.value = this.time_range
    this.optionsChangedCB()
  }

  onFrequencyChanged(event)
  {
    let f = Math.abs(parseFloat(event.currentTarget.value))
    this.update_frequency = Math.min(Math.max(5, f), 60)
    event.currentTarget.value = this.update_frequency
    this.update_period = 1 / this.update_frequency
    this.optionsChangedCB()
  }

  getOptionsJsonString()
  {
    return JSON.stringify({"n": this.num_samples, 
      "time_range": this.time_range, 
      "f": this.update_frequency})
  }

  getColor(index)
  {
    return this.line_colors[index % this.line_colors.length]
  }

  /*
  plot(keys, values, module_changed)
  {
    this.updateLines(keys, values)

    while(this.ts.length > this.num_samples) this.ts.shift()
    this.ts.push(values[0])

    for(let i = 0; i < values.length; i++)
    {
      while(this.data[i].length > this.num_samples) this.data[i].shift()
      this.data[i].push(values[i])
    }

    let last_ts = this.ts[this.ts.length - 1]

    let min_x = 100000

    for(let i = 0; i < this.data[0].length; i++)
    {
      this.data[0][i] = -(last_ts - this.ts[i]) / 1000000000

      if(this.data[0][i] < min_x) min_x = this.data[0][i]
    }

    if(min_x != 100000)
    {
      min_x = Math.round(min_x)
      //this.line_plot.setScale("x", {min: min_x, max: 0})
    }

    //this.line_plot.setData(this.data)
  }
  */

  plot(keys, values, module_changed)
  {
    this.updateLines(keys, values, module_changed)

    let t = 0.0

    //compute plot time of new sample
    if(this.data[0].length > 0 && this.last_ts != 0)
    {
      let last_t = this.data[0][this.data[0].length - 1]
      let dt = (values[0] - this.last_ts) / 1000000000
      t = last_t + dt

      //compute correction time for plot if diverged too much
      if(Math.abs(t) > 0.5) 
      {
        //console.log("Time divergence at: " + t.toString())
        if(this.t_correction == 0) this.t_correction = -t
      }
    }

    //store current ts as last ts
    this.last_ts = values[0]

    //push new sample
    for(let i = 0; i < values.length; i++)
    {
      this.data[i].push(i == 0 ? t : values[i])
    }

    //remove old samples
    if(this.data[0].length > 0)
    {
      while(this.data[0].length > this.num_samples || this.data[0][1] < -this.time_range)
      {
        for(let i = 0; i < this.data.length; i++)
        {
          this.data[i].shift()
        }
      }
    }
  }

  animationUpdate(time_stamp)
  {
    if(this.last_animation_ts == -1)
    {
      this.last_animation_ts = time_stamp
    }

    //compute delta time since last animation frame in seconds
    let dt = (time_stamp - this.last_animation_ts)/1000.0

    //store current time stamp as last
    this.last_animation_ts = time_stamp

    //accumulate elapsed time
    this.dt_accum += dt

    //console.log(dt)

    if(this.update_frequency == 60.0) this.update_period = 0.0

    //update data
    if(this.data[0] != undefined && this.data[0].length > 0 && this.dt_accum >= this.update_period)
    {
      //advance by elapsed time
      dt = -this.dt_accum + this.t_correction

      //move all samples by dt
      for(let i = 0; i < this.data[0].length; i++)
      {
        this.data[0][i] += dt
      }

      //update plot with new timestamps
      this.line_plot.setData(this.data)

      //reset elapsed time
      this.dt_accum = 0.0

      this.frame_cnt++;

      //reset time correction
      this.t_correction = 0
    }

    
    
    //request next animation frame
    window.requestAnimationFrame(this.animationUpdate.bind(this))
  }

  updateLines(keys, values, module_changed)
  {
    if(keys.length != this.num_lines || module_changed)
    {
      this.removeAllLines()
      this.data = [[]]
      let legend = []
      this.all_channels = []
      this.ts = []

      for(let i = 1; i < keys.length; i++)
      {
        //console.log("create series: " + i.toString())
        this.line_plot.addSeries({stroke: this.getColor(i-1)}, i)
        this.data.push([])
        legend.push([keys[i], this.getColor(i-1)])
        this.all_channels.push(keys[i])
      }

      this.num_lines = keys.length

      this.create_legend(this.legend_div, legend)
    }
  }

  removeAllLines()
  {
    for(let i = 1; i < this.num_lines; i++)
    {
      //console.log("del series: " + i.toString())
      this.line_plot.delSeries(1)
    }

    this.num_lines = 0
  }

  resize(w, h)
  {
    //prevent scroll bars
    w -= 1
    h -= 1

    //update plot size
    this.line_plot.setSize({width:w, height:h})
  }

  reset()
  {
    //this.table.innerHTML = ""
  }
}