
class VideoStreamPlot extends Plot
{
  constructor(plot_div, legend_div, options_div, plot_options)
  {
    super();
    this.plot_div = plot_div
    this.legend_div = legend_div
    this.options_div = options_div
    this.current_video_stream_url = ""

    this.iframe = document.createElement("iframe")
    //this.iframe.src = "http://172.20.8.231:8889/cam1/"
    this.iframe.className = "video-stream-iframe"
    this.plot_div.appendChild(this.iframe)
  }

  plot_video_stream(video_stream_url)
  {
    if (!video_stream_url.startsWith("http://") &&
        !video_stream_url.startsWith("https://")) {
      video_stream_url = "http://" + video_stream_url
    }

    console.log("PLOT VIDEO STREAM: " + video_stream_url)

    if(video_stream_url == "")
    {
      if(video_stream_url != this.current_video_stream_url)
      {
        this.current_video_stream_url = ""
        this.iframe.src = ""
      }
    }

    if(video_stream_url != this.current_video_stream_url)
    {
      this.current_video_stream_url = video_stream_url
      this.iframe.src = this.current_video_stream_url
    }
  }

  reset()
  {
    this.table.innerHTML = ""
  }
}