
class ImagePlot extends Plot
{
  constructor(plot_div, legend_div, options_div, plot_options)
  {
    super();
    this.plot_div = plot_div
    this.legend_div = legend_div
    this.options_div = options_div
  }

  plot_image(image_str, resolution_x, resolution_y)
  {
    this.plot_div.innerHTML = ""
    let preview_image = new Image(resolution_x, resolution_y)
    preview_image.src = "data:image/jpeg;base64," + image_str
    preview_image.setAttribute("class","preview-image")
    this.plot_div.appendChild(preview_image)
  }

  reset()
  {
    this.table.innerHTML = ""
  }
}