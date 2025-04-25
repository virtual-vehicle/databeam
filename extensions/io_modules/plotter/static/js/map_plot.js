class MapPlot extends Plot {
    constructor(plot_div, legend_div, options_div, plot_options) {
        super();
        this.plot_div = plot_div
        this.legend_div = legend_div
        this.options_div = options_div

        let map_div = document.createElement("div")
        map_div.setAttribute("class", "map-div")
        this.plot_div.appendChild(map_div)

        //holds data
        this.data = []
        this.opt_max_samples = plot_options.hasOwnProperty("max_samples") ? plot_options["max_samples"] : 100
        this.opt_center_latest_location = plot_options.hasOwnProperty("center_latest_location") ? plot_options["center_latest_location"] : false

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

    addOption(header_str, form) {
        let header = document.createElement("h3")
        header.innerHTML = header_str

        let div = document.createElement("div")
        div.setAttribute("class", "option-row");
        div.appendChild(header)
        div.appendChild(form)
        this.options_div.appendChild(div)
    }

    createOptions(div) {
        console.log("Update Plot Options")
        this.options_div = div
        this.options_div.innerHTML = ""
        this.addOption("Max Samples",
            Utils.createNumberInput(this.opt_max_samples,
                event => this.onMaxSamplesChanged(event)))
        this.addOption("Center Latest Location",
            Utils.createCheckBox([], this.opt_center_latest_location,
                event => this.onCenterLatestLocationChanged(event)))
    }

    getOptionsJsonString() {
        return JSON.stringify({
            "max_samples": this.opt_max_samples,
            "center_latest_location": this.opt_center_latest_location
        })
    }

    onMaxSamplesChanged(event) {
        let n = parseFloat(event.currentTarget.value)
        this.opt_max_samples = Math.min(Math.max(1, n), 500)
        event.currentTarget.value = this.opt_max_samples
        this.optionsChangedCB()
    }

    onCenterLatestLocationChanged(event) {
        this.opt_center_latest_location = Boolean(event.currentTarget.checked)
        this.optionsChangedCB()
    }

    plot_map(lat, lon) {
        // console.log("Plot map: " + lat.toString() + ", " + lon.toString())

        // add new data to the beginning of the array
        this.data.unshift([lat, lon])
        // remove oldest data
        if (this.data.length > this.opt_max_samples) {
            this.data.pop();
        }
        // update the polyline
        this.polyline.setLatLngs(this.data);

        // zoom the map to the polyline
        // this.map.fitBounds(polyline.getBounds());
        if (this.opt_center_latest_location) {
            this.map.setView([this.data[0][0], this.data[0][1]], this.map.getZoom());
        }
    }

    reset() {
        this.table.innerHTML = ""
    }
}
