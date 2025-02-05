
class MapPlot extends Plot
{
  constructor(plot_div, legend_div, options_div, plot_options)
  {
    super();
    this.plot_div = plot_div
    this.legend_div = legend_div
    this.options_div = options_div

    let map_div = document.createElement("div")
    map_div.setAttribute("class", "map-div")
    this.plot_div.appendChild(map_div)

    //holds data
    this.data = []

    //holds the line plot instance
    this.map = L.map(map_div).setView([47.0581156667, 15.4622731667], 19);

    L.control.scale().addTo(this.map);

    this.polyline = L.polyline(this.data, {color: 'red'}).addTo(this.map);

    // openstreetmap tiles
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxNativeZoom: 19,
      maxZoom: 30,
      attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a>'
    }).addTo(this.map);

    // L.tileLayer('https://tiles.stadiamaps.com/tiles/stamen_toner/{z}/{x}/{y}{r}.{ext}', {
    //   minZoom: 0,
    //   maxNativeZoom: 20,
    //   maxZoom: 30,
    //   opacity: 0.5,
    //   attribution: '&copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://www.stamen.com/" target="_blank">Stamen Design</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    //   ext: 'png'
    // }).addTo(this.map);

    // L.tileLayer('https://tiles.stadiamaps.com/tiles/alidade_satellite/{z}/{x}/{y}{r}.{ext}', {
    //   minZoom: 0,
    //   maxNativeZoom: 21,
    //   maxZoom: 30,
    //   attribution: '&copy; CNES, Distribution Airbus DS, © Airbus DS, © PlanetObserver (Contains Copernicus Data) | &copy; <a href="https://www.stadiamaps.com/" target="_blank">Stadia Maps</a> &copy; <a href="https://openmaptiles.org/" target="_blank">OpenMapTiles</a> &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    //   ext: 'jpg'
    // }).addTo(this.map);

    // log zoom level
    this.map.on('zoomend', function (e) {
      console.log("zoom: " + e.target._zoom);
    });

    // https://forum.ionicframework.com/t/leaflet-map-not-showed-properly/204854/4
    // for correct initial drawing
    this.map.whenReady(() => {
      setTimeout(() => {
        console.log("ready")
        this.map.invalidateSize();
      }, 100);
    });
  }

  plot_map(lat, lon)
  {
    // console.log("Plot map: " + lat.toString() + ", " + lon.toString())

    // add new data to the beginning of the array
    this.data.unshift([lat, lon])
    // remove oldest data
    if (this.data.length > 100) {
      this.data.pop();
    }
    // update the polyline
    this.polyline.setLatLngs(this.data);

    // zoom the map to the polyline
    // this.map.fitBounds(polyline.getBounds());
  }

  reset()
  {
    this.table.innerHTML = ""
  }
}
