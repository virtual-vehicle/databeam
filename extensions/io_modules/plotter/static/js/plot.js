
class Plot
{
  constructor()
  {

  }

  plot(keys, values)
  {

  }

  plot_image(image_str, resolution_x, resolution_y)
  {

  }

  plot_spectrum(data)
  {
    
  }

  resize(w, h)
  {

  }

  reset()
  {

  }

  set_module_meta(meta)
  {

  }

  createOptions(div)
  {
    div.innerHTML = "This plot type does not provide additional settings."
  }

  getOptionsJsonString()
  {
    return JSON.stringify({})
  }

  bindOptionsChangedCB(callback) { this.optionsChangedCB = callback }

  create_legend(legend_div, data)
  {
    legend_div.innerHTML = ""
    let group_div = document.createElement("div")
    group_div.setAttribute("class", "legend-row")

    for(let i = 0; i < data.length; i++)
    {
      let label = data[i][0]
      let color = data[i][1]
      let label_div = document.createElement("div")
      label_div.innerHTML = label
      label_div.setAttribute("class", "legend-item-div")
      label_div.style.border = "2px solid " + color
      group_div.appendChild(label_div)
    }

    legend_div.appendChild(group_div)
  }
}