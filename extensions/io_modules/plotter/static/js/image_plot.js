
class ImagePlot extends Plot
{
  constructor(plot_div, legend_div, options_div, plot_options)
  {
    super();
    this.plot_div = plot_div
    this.legend_div = legend_div
    this.options_div = options_div

    this.use_canvas = false
      
    //create image once
    
    if(!this.use_canvas)
    {
      this.preview_image = new Image(100, 100)
      this.preview_image.setAttribute("class","preview-image")
      this.plot_div.appendChild(this.preview_image)
    }
    else
    {
      this.canvas = document.createElement('canvas');
      this.canvas.setAttribute("class","preview-image")
      this.ctx = this.canvas.getContext('2d');
      this.plot_div.innerHTML = "";  // clear container
      this.plot_div.appendChild(this.canvas);
      this.canvas.width = 100
      this.canvas.height = 100
      
      this.img = new Image();
      this.img.onload = () => {
        this.ctx.drawImage(this.img, 0, 0, this.canvas.width, this.canvas.height);
      };
    }
  }

  plot_image(image_str, resolution_x, resolution_y)
  {
    //original version
    /*
    this.plot_div.innerHTML = ""
    let preview_image = new Image(resolution_x, resolution_y)
    preview_image.src = "data:image/jpeg;base64," + image_str
    preview_image.setAttribute("class","preview-image")
    this.plot_div.appendChild(preview_image)
    */

    //version 2
    if(!this.use_canvas)
    {
      if(this.preview_image.width !== resolution_x || this.preview_image.height !== resolution_y)
      {
        this.preview_image.width = resolution_x
        this.preview_image.height = resolution_y
      }

      //update image source
      this.preview_image.src = "data:image/jpeg;base64," + image_str
    }
    else
    {
      if (this.canvas.width !== resolution_x || this.canvas.height !== resolution_y) {
        this.canvas.width = resolution_x;
        this.canvas.height = resolution_y;
      }

      this.img.src = "data:image/jpeg;base64," + image_str;
    }
  }

  reset()
  {
    this.table.innerHTML = ""
  }
}