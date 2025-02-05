
class OscilloscopePlot extends Plot
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
    this.ts_key = plot_options.hasOwnProperty("ts_key") ? plot_options["ts_key"] : "rel_time"

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
          /*range: (self_p, tmin, tmax) => {
            return [0.0, 1.0]
          }*/
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
    this.data = [];
    this.ts_diff_list = [];

    this.last_ts = 0;
    this.curr_ts = 0;
    this.median_ts_diff_list = 0;

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

    this.t_correction = 0
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
    this.addOption("Array Timestamp Key", Utils.createTextInput(this.ts_key, event => this.onTsKeyChanged(event)))
  }

  onTsKeyChanged(event)
  {
    // Not yet anything to do...
  }

  onMinXChanged(event)
  {
    let t = Math.abs(parseFloat(event.currentTarget.value))
    this.time_range = Math.min(Math.max(2, t), 120)
    event.currentTarget.value = this.time_range
    this.optionsChangedCB()
  }

  getOptionsJsonString()
  {
    return JSON.stringify({"ts_key": this.ts_key})
  }

  getColor(index)
  {
    return this.line_colors[index % this.line_colors.length]
  }

  /*
   * Plots the data in different ways depending on if the ts_key field exists.
   */
  plot(keys, values)
  {
    this.updateLines(keys, values)

    let rel_time_key_exists = keys.indexOf(this.ts_key) !== -1;
    if(rel_time_key_exists)
    {
        this.plotRelTimedArray(keys, values);
    }
    else
    {
        this.plotGeneralArray(keys, values);
    }
  }

  /*
   * Plots the data correctly positioned with timestamps, if a ts_key field was found.
   */
  plotRelTimedArray(keys, values)
  {
    let rel_time_i = keys.indexOf(this.ts_key);
    let time_array = values[rel_time_i];
    let first_ts = time_array[0];
    let last_ts = time_array[time_array.length - 1];

    this.data.push(time_array);
    for(let i = 1; i < keys.length; i++)
    {
      this.data.push(values[i]);
    }

    this.line_plot.setData(this.data);
    this.data = [];
  }

  /*
   * If no ts_key field was found, all values are sequentially mapped on the x-axis between 0 and 1.
   */
  plotGeneralArray(keys, values)
  {
    let time_array = [];
    for(let i = 0; i < values[1].length; i++)
    {
      // The 0.005 are for cosmetic reasons. Otherwise the plot would not show the 1 at the right hand side.
      time_array.push(i / values[1].length + 0.005);
    }
    this.data.push(time_array);
    for(let i = 1; i < keys.length; i++)
    {
      this.data.push(values[i]);
    }

    this.line_plot.setData(this.data);
    this.data = [];
  }

  updateLines(keys, values)
  {
    // If there are multiple keys, prohibit the ts_key from being plotted.
    // It is only used as a ground truth timebase.
    let keys_copy = keys.map((x) => x);
    if(keys_copy.length > 1)
    {
      let rel_time_i = keys_copy.indexOf(this.ts_key);
      if(rel_time_i !== -1)
      {
        keys_copy.splice(rel_time_i, 1);
      }
    }
    // If rel_time is the only field, rename it to allow plotting it.
    // The name "rel_time" is reserved for the time estimation of the oscilloscope data.
    else
    {
      keys[0] = this.ts_key + "_";
    }

    if(keys_copy.length != this.num_lines)
    {
      this.removeAllLines()
      this.data = []
      let legend = []
      this.all_channels = []
      this.ts = []

      for(let i = 1; i < keys_copy.length; i++)
      {
        //console.log("create series: " + i.toString())
        this.line_plot.addSeries({stroke: this.getColor(i-1)}, i)
        this.data.push([])
        legend.push([keys[i], this.getColor(i-1)])
        this.all_channels.push(keys_copy[i])
      }

      this.num_lines = keys_copy.length

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