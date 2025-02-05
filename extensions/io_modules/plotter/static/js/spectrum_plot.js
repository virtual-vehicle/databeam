
class SpectrumPlot extends Plot
{
  constructor(plot_div, legend_div, options_div, plot_options)
  {
    super();
    this.plot_div = plot_div
    this.legend_div = legend_div
    this.options_div = options_div

    //read config parameters
    this.x_min = plot_options.hasOwnProperty("x_min") ? plot_options["x_min"] : 0
    this.x_max = plot_options.hasOwnProperty("x_max") ? plot_options["x_max"] : 2048
    this.y_min = plot_options.hasOwnProperty("y_min") ? plot_options["y_min"] : 0
    this.y_max = plot_options.hasOwnProperty("y_max") ? plot_options["y_max"] : 65536

    this.x_range_min = 0.0
    this.x_range_max = 2048.0

    //holds x axis data
    this.x_data = []

    let self = this

    //define opts for plot
    this.opts = {
      title: "",
      width: 500,
      height: 500,
      pxAlign: 1,
      scales: {
        x: {
          time: false,
          auto: true,

          range: (self_p, tmin, tmax) => {
            return [self.x_min, self.x_max]
          }
        },
        y: {
        	auto: true,
          //range: [0.0, self.y_max]
          range: (self_p, tmin, tmax) => {
            return [self.y_min, self.y_max]
          }
        }
      },
      series: [
        {},
        {
          stroke: "blue",
          paths: uPlot.paths.stepped({align: 1}),
          points: {
            show: false
          }
        },
        {
          stroke: "orange",
          paths: uPlot.paths.stepped({align: 1}),
          points: {
            show: false
          }
        },
      ],
      hooks: {
        setSelect: [
          u => {
            if (u.select.width > 0) 
            {
              let xmin = u.posToVal(u.select.left, 'x');
              let xmax = u.posToVal(u.select.left + u.select.width, 'x');
              self.x_min = xmin
              self.x_max = xmax
            }
            else
            {
              self.x_max = self.x_range_max
              self.x_min = self.x_range_min
            }

            self.optionsChangedCB()
          }
        ]
      },
      legend: {
        show: false
      }
    };

    //holds data
    this.data = []

    //holds the line plot instance
    this.bar_plot = new uPlot(this.opts, this.data, this.plot_div);
  }

  addOption(header_str, forms_list)
  {
    let header = document.createElement("h3")
    header.innerHTML = header_str

    let div = document.createElement("div")
    div.setAttribute("class", "option-row");
    div.appendChild(header)
    for(let i = 0; i < forms_list.length; i++) div.appendChild(forms_list[i])
    this.options_div.appendChild(div)
  }

  createOptions(div)
  {
    console.log("Create options")

    //number of samples
    this.options_div = div
    this.options_div.innerHTML = ""

    this.addOption("Y Min", [Utils.createNumberInput(this.y_min, event => this.onYMinChanged(event))])
    this.addOption("Y Max", [Utils.createNumberInput(this.y_max, event => this.onYMaxChanged(event))])
  }

  onYMinChanged(event)
  {
    let n = parseFloat(event.currentTarget.value)
    this.y_min = Math.min(Math.max(-65536, n), 65536)
    event.currentTarget.value = this.y_min
    this.optionsChangedCB()
  }

  onYMaxChanged(event)
  {
    let n = parseFloat(event.currentTarget.value)
    this.y_max = Math.min(Math.max(0, n), 65536)
    event.currentTarget.value = this.y_max
    this.optionsChangedCB()
  }

  getOptionsJsonString()
  {
    return JSON.stringify({ 
      "x_min": this.x_min,
      "x_max": this.x_max,
      "y_min": this.y_min,
      "y_max": this.y_max
    })
  }

  set_module_meta(meta)
  {
    console.log("Set Meta")

    if(meta.hasOwnProperty("wavelengths_live"))
    {
      this.x_data = meta['wavelengths_live']
      this.x_range_min = this.x_data[0]
      this.x_range_max = this.x_data[this.x_data.length - 1]
      this.x_min = Utils.clamp(this.x_min, this.x_range_min, this.x_range_max)
      this.x_max = Utils.clamp(this.x_max, this.x_range_min, this.x_range_max)
    }
  }

  plot_spectrum(intensity, absorbance)
  {
    //make sure x data length matches y data length
    if(this.x_data.length != intensity.length)
    {
      this.x_data = Array.from({length: intensity.length}, (v, i) => i)
    }
    this.bar_plot.setData([this.x_data, intensity, absorbance])
  }

  resize(w, h)
  {
    //prevent scroll bars
    w -= 1
    h -= 1

    //update plot size
    this.bar_plot.setSize({width:w, height:h})
  }

  reset()
  {
    this.table.innerHTML = ""
  }
}