class View 
{
  constructor() 
  {
    console.log('Creating View.')
    let self = this

    //module log overlay
    this.last_module_log_name = ""

    //form id counter to prevent warnings due to missing form ids
    this.form_id_counter = 0

    //module log div
    document.getElementById('log_alert_id').addEventListener(
      "click", event => this.onShowModuleLogOverlay(event), true);

    document.getElementById('clear_module_log_button_id').addEventListener(
      "click", event => this.onClearModuleLogOverlay(event), true);

    document.getElementById('close_module_log_button_id').addEventListener(
      "click", event => this.onCloseModuleLogOverlay(event), true);

    //left div
    document.getElementById('start_sampling_button_id').addEventListener(
      "click", event => this.onStartSampling(event), true);

    document.getElementById('stop_sampling_button_id').addEventListener(
      "click", event => this.onStopSampling(event), true);

    document.getElementById('start_button_id').addEventListener(
      "click", event => this.onStart(event), true);

    document.getElementById('stop_button_id').addEventListener(
      "click", event => this.onStop(event), true);

    document.getElementById('run_tag_id').addEventListener(
      "change", event => this.onSubmitRunTag(event), true);

    document.getElementById('runid_id').addEventListener(
      "change", event => this.onSubmitRunID(event), true);
    
    //tabs
    document.getElementById('modules_tab_button_id').addEventListener(
      "click", event => this.switchTab("modules_div_id"), true);

    document.getElementById('data_tab_button_id').addEventListener(
      "click", event => this.switchTab("data_div_id"), true);

    document.getElementById('system_tab_button_id').addEventListener(
      "click", event => this.switchTab("system_div_id"), true);

    //module config
    document.getElementById('show_meta_button_id').addEventListener(
      "click", event => this.onShowMeta(event), true);

    document.getElementById('config_layout_button_id').addEventListener(
      "click", event => this.onConfigLayoutButtonClick(event), true);

    document.getElementById('simple_config_button_id').addEventListener(
      "click", event => this.onSimpleConfigButtonClick(event), true);

    document.getElementById('advanced_config_button_id').addEventListener(
      "click", event => this.onAdvancedConfigButtonClick(event), true);

    document.getElementById('apply_config_button_id').addEventListener(
      "click", event => this.onApplyConfigButtonClick(event), true);

    document.getElementById('store_config_button_id').addEventListener(
      "click", event => this.onStoreConfigButtonClick(event), true);

    document.getElementById('load_config_button_id').addEventListener(
      "click", event => this.onLoadConfigButtonClick(event), true);

    document.getElementById('load_config_file_id').addEventListener(
      "change", event => this.onLoadConfigFileChanged(event), true);

    document.getElementById('default_config_button_id').addEventListener(
      "click", event => this.onDefaultConfigButtonClick(event), true);

    document.getElementById('config_inspector_id').addEventListener(
      "change", event => this.onConfigTextAreaChanged(event), true);

    //preview
    document.getElementById('preview_topic_id').addEventListener(
      "change", event => this.onPreviewTopicSelectionChanged(event), true);

    //data tab
    document.getElementById('download_measurements_button_id').addEventListener(
      "click", event => this.onDownloadMeasurements(event), true);

    document.getElementById('remove_measurenemts_button_id').addEventListener(
      "click", event => this.onRemoveMeasurements(event), true);

    document.getElementById("docker_log_info_id").addEventListener(
      "click", event => this.onDockerLogCheckBoxClick(event, 0), true);

    document.getElementById("docker_log_warning_id").addEventListener(
      "click", event => this.onDockerLogCheckBoxClick(event, 1), true);

    document.getElementById("docker_log_debug_id").addEventListener(
      "click", event => this.onDockerLogCheckBoxClick(event, 2), true);

    document.getElementById("docker_log_error_id").addEventListener(
      "click", event => this.onDockerLogCheckBoxClick(event, 3), true);

    // system buttons
    document.getElementById('docker_restart_button_id').addEventListener(
      "click", event => this.customConfirm("Docker Restart", "Do you want to restart docker containers?",
      () => { this.controller.postSystemCommand("docker_restart") }), true);

    document.getElementById('docker_pull_button_id').addEventListener(
      "click", event => this.customConfirm("Docker Pull", "Do you want to pull docker images?",
      () => { this.controller.postSystemCommand("docker_pull") }), true);

    document.getElementById('time_sync_button_id').addEventListener(
      "click", event => this.customConfirm("Time Synchronization", "Do you want to synchronize time?",
      () => { this.controller.postSystemCommand("time_sync") }), true);

    document.getElementById('reboot_button_id').addEventListener(
      "click", event => this.customConfirm("Reboot", "Do you want to reboot the system?",
      () => { this.controller.postSystemCommand("reboot") }), true);

    document.getElementById('shutdown_button_id').addEventListener(
      "click", event => this.customConfirm("Shutdown", "Do you want to shutdown the system?",
      () => { this.controller.postSystemCommand("shutdown") }), true);

    document.getElementById('docker_download_logs_button_id').addEventListener(
      "click", event => this.controller.onDownloadDockerLogs(), true);

    document.getElementById("theme_select_id").addEventListener(
      "change", event => this.onThemeSelectChanged(event), true);
  }

  init(controller, model)
  {
    //store model and controller references
    this.controller = controller
    this.model = model

    //init databeam url and database url
    let host_zero = window.location.hostname.length == 0
    //this.model.setDataBeamURL(host_zero ? "localhost:5000" : window.location.hostname + ":" + window.location.port)
    this.model.setDataBeamIP(host_zero ? "localhost" : window.location.hostname)

    //show modules tab as default
    document.getElementById('modules_tab_button_id').click()

    let self = this
    document.getElementById("overlay_div_id").addEventListener('animationend', () => {
      if(self.model.getOnlineStatus())
      {
        document.getElementById("overlay_div_id").style.display = "none"
      }
    });

    this.onModelThemeChanged()
    this.updateConfigLayoutButton()
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

  customConfirm(header, message, confirm_callback)
  {
    document.getElementById("alert_header_id").innerHTML = header
    document.getElementById("alert_message_div_id").innerHTML = message

    let alert_overlay_div = document.getElementById("alert_overlay_div_id")
    alert_overlay_div.style.display = "flex"
    alert_overlay_div.style.animationName = "alert-overlay-div-fade-in"

    let buttons_div = document.getElementById("alert_buttons_div_id")
    buttons_div.innerHTML = ""

    if(confirm_callback != undefined)
    {
      var confirm_button = document.createElement("BUTTON");
      confirm_button.innerHTML = "Confirm"
      confirm_button.className = "config-buttons"
      confirm_button.addEventListener(
        "click", event => this.customConfirmButtonClick(event, confirm_callback), true);
      buttons_div.appendChild(confirm_button)
    }

    var abort_button = document.createElement("BUTTON");
    abort_button.innerHTML = confirm_callback == undefined ? "OK" : "Abort"
    abort_button.className = "config-buttons"
    abort_button.addEventListener(
      "click", event => this.customConfirmAbortButtonClick(event), true);
    buttons_div.appendChild(abort_button)
  }

  customConfirmButtonClick(event, confirm_callback)
  {
    console.log("Confirmed!")
    let alert_overlay_div = document.getElementById("alert_overlay_div_id")
    alert_overlay_div.style.animationName = "alert-overlay-div-fade-out"
    confirm_callback()
  }

  customConfirmAbortButtonClick(event)
  {
    console.log("Aborted!")
    let alert_overlay_div = document.getElementById("alert_overlay_div_id")
    alert_overlay_div.style.animationName = "alert-overlay-div-fade-out"
  }

  onDockerLogCheckBoxClick(event, log_type)
  {
    let checked = event.currentTarget.checked
    console.log("View:onDockerLogCheckBoxClick(" + log_type.toString() + ", " + checked + ")")
    this.model.setDockerLogsFilter(log_type, event.currentTarget.checked)
  }

  onErrorMessage(title, message)
  {
    this.customConfirm(title, message, undefined)
  }

  onStartSampling(callback) 
  {
    this.controller.startSampling()
  }

  onStopSampling(callback) 
  {
    this.controller.stopSampling()
  }

  onStart(callback) 
  {
    this.controller.start()
  }

  onStop(callback) 
  {
    this.controller.stop()
  }

  onSubmitRunTag(event)
  {
    this.controller.updateSystemMeta({run_tag: document.getElementById('run_tag_id').value})
  }

  onSubmitRunID(event)
  {
    let run_id_str = document.getElementById('runid_id').value
    let run_id = run_id_str == "" ? 0 : Math.max(0, parseInt(run_id_str))
    this.controller.updateSystemMeta({run_id: run_id})
  }

  switchTab(name)
  {
    let tabs = [['modules_div_id', 'modules_tab_button_id'], 
                ['data_div_id', 'data_tab_button_id'],
                ['system_div_id', 'system_tab_button_id']]

    for(let i = 0; i < tabs.length; i++)
    {
      let div = document.getElementById(tabs[i][0])
      let button = document.getElementById(tabs[i][1])
      let s = name == tabs[i][0]
      div.style.display = s ? 'flex' : 'none'
      button.style.boxShadow = s ? '0px 0px 2px 2px var(--heading_color) inset' : ''
    }

    this.controller.onTabSwitched(name)
  }

  createTableHeader(table, header_labels, styles=undefined)
  {
    if(table.querySelector('thead') == null)
    {
      //create table header and header labels array
      let thead = document.createElement("thead");

      //create header cells
      for(let i = 0; i < header_labels.length; i++)
      {
        let th = document.createElement("th")

        if(typeof(header_labels[i]) == "object")
        {
          th.appendChild(header_labels[i])
        }
        else
        {
          th.innerHTML = header_labels[i]
        }

        //apply th styles
        if(styles != undefined)
        {
          let style_dict = styles[i]

          for(const [key, value] of Object.entries(style_dict))
          {
            th.style[key] = value
          }
        }
        
        thead.appendChild(th)
      }

      //create table body, append header and body to table
      let tbody = document.createElement("tbody");
      table.appendChild(thead)
      table.appendChild(tbody)
    }
  }

  createCheckBox(attributes, checked)
  {
    let checkbox = document.createElement("INPUT");
    checkbox.setAttribute("type", "checkbox");
    for(let i = 0; i < attributes.length; i++) checkbox.setAttribute(attributes[i][0], attributes[i][1])
    checkbox.checked = checked
    return checkbox
  }

  createEmojiButton(attributes, emoji_str)
  {
    let button = document.createElement("BUTTON")
    button.innerHTML = emoji_str
    button.setAttribute("class", "emoji-button")
    for(let i = 0; i < attributes.length; i++) button.setAttribute(attributes[i][0], attributes[i][1])
    return button
  }

  onShowMeta(event)
  {
    console.log("what")
    let meta_div = document.getElementById('meta_div_id')

    let is_enabled = meta_div.style.display != "none"
    event.currentTarget.innerHTML = is_enabled ? "Show Meta" : "Hide Meta"
    meta_div.style.display = is_enabled ? "none" : "flex"
  }

  onMetaChanged()
  {
    //get meta
    let system_meta = this.model.getSystemMeta()
    let user_meta = this.model.getUserMeta()

    //set run_tag and run_id values
    document.getElementById('run_tag_id').value = system_meta.run_tag
    document.getElementById('runid_id').value = system_meta.run_id

    //get and clear devices table
    let table = document.getElementById('meta_table_id')

    //create table header
    const header_labels = ["Key", "Value", "Remove"]
    this.createTableHeader(table, header_labels)

    //get table body
    let table_body = table.querySelector('tbody')

    //leave if there is no metadata
    if(user_meta.length == 0) return

    //delete unused rows
    let n = table_body.rows.length - user_meta.length
    for(let i = 0; i < n; i++) table_body.deleteRow(-1);

    //iterate user meta
    for(let i = 0; i < user_meta.length; i++)
    {
      let key = user_meta[i].getKey()
      let value = user_meta[i].getValue()

      if(table_body.rows.length > i)
      {
        //use existing row
        table_body.rows[i].cells[0].firstChild.value = key
        table_body.rows[i].cells[1].firstChild.value = value
        table_body.rows[i].cells[1].firstChild.disabled = key == ""
        table_body.rows[i].cells[2].firstChild.setAttribute("meta-key", key)
        table_body.rows[i].cells[2].firstChild.disabled = key == ""
      }
      else
      {
        //insert row
        let row = table_body.insertRow()

        //create text input field for meta key
        let key_text_input = document.createElement("INPUT")
        key_text_input.name = this.getNextFormIDString()
        key_text_input.setAttribute("type", "text")
        key_text_input.setAttribute("class", "meta-input-form")
        key_text_input.value = key
        key_text_input.placeholder = "<Key>"
        key_text_input.addEventListener("change", event => this.onMetaEntryChanged(event));
        row.insertCell().appendChild(key_text_input)

        //create text input field for meta value
        let value_text_input = document.createElement("INPUT")
        value_text_input.name = this.getNextFormIDString()
        value_text_input.setAttribute("type", "text")
        value_text_input.setAttribute("class", "meta-input-form")
        value_text_input.value = value
        value_text_input.placeholder = "<Value>"
        value_text_input.disabled = key == ""
        value_text_input.addEventListener("change", event => this.onMetaEntryChanged(event));
        row.insertCell().appendChild(value_text_input)

        //create show config button
        let remove_button = this.createEmojiButton([['meta-key', key]], "&#128293;")
        remove_button.addEventListener("click", event => this.onRemoveMeta(event), true);
        remove_button.disabled = key == ""
        row.insertCell().appendChild(remove_button)
      }
    }
  }

  timeDeltaToString(time_delta)
  {
    let abs_time_delta = Math.abs(time_delta)
    if(abs_time_delta < 60) return time_delta.toString() + "s"
    if(abs_time_delta < 3600) return Math.round(time_delta / 60).toString() + "m"
    if(abs_time_delta < 86400) return Math.round(time_delta / 3600).toString() + "h"
    if(abs_time_delta < 31557600) return Math.round(time_delta / 86400).toString() + "d"
    return Math.round(time_delta / 31557600).toString() + "y"
  }

  onStateJobChanged()
  {
    let state_job = this.model.getStateJob()
    let capture = state_job.data.capture
    let sampling = state_job.data.sampling

    document.getElementById('start_button_id').disabled = capture;
    document.getElementById('stop_button_id').disabled = !capture;
    document.getElementById('start_sampling_button_id').disabled = sampling || capture;
    document.getElementById('stop_sampling_button_id').disabled = !sampling || capture;
    document.getElementById('sampling_icon_id').style.display = !capture && sampling ? "flex" : "none" 
    document.getElementById('capture_icon_id').style.display = capture ? "flex" : "none" 
  }

  onLogJob(log_job)
  {
    let job_container = document.getElementById("log_job_id")
    document.getElementById("log_alert_id").style.display = "flex"

    if(this.last_module_log_name != log_job.name)
    {
      this.last_module_log_name = log_job.name
      let message_header = document.createElement("h2")
      message_header.innerHTML = log_job.name
      job_container.appendChild(message_header)
    }
    
    let message_div = document.createElement("p")
    message_div.innerHTML = "<b>" + log_job.time_str + "</b> | " + log_job.message
    message_div.setAttribute("class", "p-debug")
    job_container.appendChild(message_div)
  }

  onShowModuleLogOverlay(event)
  {
    let sidebar_div = document.getElementById("log_sidebar_div_id")
    sidebar_div.style.display = "block"
  }

  onClearModuleLogOverlay(event)
  {
    let job_container = document.getElementById("log_job_id")
    job_container.innerHTML = ""
    this.last_module_log_name = ""

    document.getElementById("log_alert_id").style.display = "none"
  }

  onCloseModuleLogOverlay(event)
  {
    let sidebar_div = document.getElementById("log_sidebar_div_id")
    sidebar_div.style.display = "none"
  }

  onJobsChanged()
  {
    //set databeam time
    let time_delta = Math.round((this.model.getDataBeamTimeNS() / 1000000000) - (Date.now() / 1000))
    let time_flag = Math.abs(time_delta) > 1 
    let time_element = document.getElementById('db_time')
    time_element.innerHTML = this.model.getDataBeamTimeString() + " UTC" + (time_flag ? " (" + this.timeDeltaToString(time_delta) + ")" : "")
    //time_element.style.color = time_flag ? "var(--docker_error_color)" : "var(--select_font_color)"

    return

    let busy_jobs = this.model.getBusyJobs()

    //get jobs div
    let job_container = document.getElementById("job_container_id")

    //holds all elements to remove
    let remove_list = []

    //holds all busy jobs that are already present
    let busy_jobs_done = []

    //iterate all children
    for(let i = 0; i < job_container.children.length; i++)
    {
      //get job id from element
      let job_id = job_container.children[i].getAttribute("job_id")

      //holds if job with id was found
      let found = false

      //search for busy job with same id
      if(job_id != null)
      {
        //iterate all busy jobs
        for(let j = 0; j < busy_jobs.length; j++)
        {
          //if job has the same id
          if(busy_jobs[j].getID().toString() == job_id)
          {
            //update the name and description
            let p_name = job_container.children[i].getElementsByTagName("h2")
            let p_description = job_container.children[i].getElementsByTagName("p")
            p_name[0].innerHTML = busy_jobs[j].getName()
            p_description[0].innerHTML = busy_jobs[j].getDescription() 
            found = !busy_jobs[i].getDone()
            busy_jobs_done.push(job_id)
            break;
          }
        }
      }

      //store element to be removed if not found
      if(!found) remove_list.push(job_container.children[i])
    }

    //remove all elements on list
    for(let i = 0; i < remove_list.length; i++) job_container.removeChild(remove_list[i])

    //iterate busy jobs
    for(let i = 0; i < busy_jobs.length; i++)
    {
      //skip job if already present
      if(busy_jobs_done.includes(busy_jobs[i].getID().toString())) continue

      //create new elements for current job
      let div = document.createElement("div")
      let p_name = document.createElement("h2")
      let busy_div = document.createElement("div")
      let p_description = document.createElement("p")

      //set the class
      div.setAttribute("class", "job-div")
      div.setAttribute("job_id", busy_jobs[i].getID().toString())

      //set job values
      p_name.innerHTML = busy_jobs[i].getName()
      busy_div.setAttribute("class", "busy-bar")
      p_description.innerHTML = busy_jobs[i].getDescription() 
      p_description.setAttribute("class", "job-p")

      //add job elements to div
      div.appendChild(p_name)
      div.appendChild(busy_div)
      div.appendChild(p_description)

      //append div to job container
      job_container.appendChild(div)
    }
  }

  onMetaEntryChanged(event)
  {
    let table = document.getElementById("meta_table_id");
    let new_meta = {}

    for(let i = 0; i < table.rows.length; i++)
    {
      let row = table.rows[i]
      let key = row.cells[0].firstChild.value
      let value = row.cells[1].firstChild.value
      if(key != "") new_meta[key] = value
    }

    this.controller.updateUserMeta(new_meta)
  }

  onRemoveMeta(event)
  {
    let table = document.getElementById("meta_table_id");
    let meta_key = event.currentTarget.getAttribute("meta-key") 
    let new_meta = {}

    for(let i = 0; i < table.rows.length; i++)
    {
      let row = table.rows[i]
      let key = row.cells[0].firstChild.value
      let value = row.cells[1].firstChild.value
      if(key != "" && key != meta_key) new_meta[key] = value
    }

    this.controller.updateUserMeta(new_meta)
  }

  onDockerLogsChanged()
  {
    let log_str = this.model.getDockerLogs()
    //log_str = log_str.replaceAll("<", "&lt;")
    //log_str = log_str.replaceAll(">", "&gt;")
    //const regex = RegExp("[0-9]/g");
    //log_str = log_str.replaceAll(/[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2},[0-9]{3}/g, "<em>$&</em>")

    let parts = log_str.split("\n")
    let result = ""

    let counts = [0, 0, 0, 0]
    let debug_flag = this.model.getDockerDebugFlag()
    let error_flag = this.model.getDockerErrorFlag()
    let warning_flag = this.model.getDockerWarningFlag()
    let info_flag = this.model.getDockerInfoFlag()

    let multi_lines = ""
    let last_type = -1;
    const p_classes = ["p-debug", "p-error", "p-warn", "p-info"]
    let type = -1

    for(let i = 0; i < parts.length; i++)
    {
      //find log level of line
      if(parts[i].includes("DEBUG"))
      {
        counts[2] += 1
        if(!debug_flag) continue
        type = 0
      }
      else if(parts[i].includes("ERROR"))
      {
        counts[3] += 1
        if(!error_flag) continue
        type = 1
      }
      else if(parts[i].includes("WARNING"))
      {
        counts[1] += 1
        if(!warning_flag) continue
        type = 2
      }
      else
      {
        if(parts[i].length == 0) continue
        counts[0] += 1
        if(!info_flag) continue
        type = 3
      }

      //store line
      if(type == last_type || last_type == -1)
      {
        multi_lines += parts[i] + "<br>"
      }
      else
      {
        result += "<p class=\"" + p_classes[last_type] + "\">" + multi_lines + "</p>"
        multi_lines = parts[i] + "<br>"
      }

      //store current type as last type
      last_type = type
    }

    //append last multi lines
    if(multi_lines != "")
    {
      result += "<p class=\"" + p_classes[last_type == -1 ? 0 : last_type] + "\">" + multi_lines + "</p>"
    }

    //set labels with count
    document.getElementById("docker_info_label_id").innerHTML = "Info (" + counts[0].toString() + ")"
    document.getElementById("docker_warning_label_id").innerHTML = "Warning (" + counts[1].toString() + ")"
    document.getElementById("docker_debug_label_id").innerHTML = "Debug (" + counts[2].toString() + ")"
    document.getElementById("docker_error_label_id").innerHTML = "Error (" + counts[3].toString() + ")"

    //set text and scroll position
    let log_text_area = document.getElementById("docker_log_id")
    let down = (log_text_area.scrollTop + log_text_area.clientHeight) == log_text_area.scrollHeight;
    log_text_area.innerHTML = result
    if(down) log_text_area.scrollTop = log_text_area.scrollHeight;
  }

  onDockerContainersChanged()
  {
    console.log("View:onDockerContainersChanged()")

    //get and clear devices table
    let table = document.getElementById('docker_table_id')
    let containers = this.model.getDockerContainers()
    let selected_id = this.model.getSelectedContainerID()

    if(containers.length == 0)
    {
      table.innerHTML = "No Docker Containers Found."
      return
    }

    //create table header (if not already present)
    const header_labels = ["ID", "Name", "Image", "Tag", "Status", "Log", "Stop"]
    this.createTableHeader(table, header_labels)

    //delete unused rows
    let n = table.rows.length - containers.length
    for(let i = 0; i < n; i++) table.deleteRow(-1);

    //iterate devices
    for(let i = 0; i < containers.length; i++)
    {
      if(table.rows.length > i)
      {
        //use existing row
        table.rows[i].cells[0].innerHTML = containers[i].getShortID()
        table.rows[i].cells[1].innerHTML = containers[i].getDisplayName()
        table.rows[i].cells[2].innerHTML = containers[i].getDisplayImage()
        table.rows[i].cells[3].innerHTML = containers[i].getDisplayTag()
        table.rows[i].cells[4].innerHTML = containers[i].getStatus()
        table.rows[i].cells[5].firstChild.setAttribute("container-id", containers[i].getShortID().toString())
        table.rows[i].cells[6].firstChild.setAttribute("container-id", containers[i].getShortID().toString())

        if(selected_id == containers[i].getShortID()){
          table.rows[i].setAttribute("class", "selected-tr")
        }
        else{
          table.rows[i].classList.remove("selected-tr")
        }
      }
      else
      {
        //append new row
        let container_row = table.insertRow()
        container_row.insertCell().innerHTML = containers[i].getShortID()
        container_row.insertCell().innerHTML = containers[i].getDisplayName()
        container_row.insertCell().innerHTML = containers[i].getDisplayImage()
        container_row.insertCell().innerHTML = containers[i].getDisplayTag()
        container_row.insertCell().innerHTML = containers[i].getStatus()

        //show container log button
        var log_button = document.createElement("BUTTON");
        log_button.innerHTML = "&#128269;"
        log_button.setAttribute("class", "emoji-button")
        log_button.id = "stop_container_button_id"
        log_button.setAttribute("container-id", containers[i].getShortID().toString())
        container_row.insertCell().appendChild(log_button)

        //stop container button
        var stop_button = document.createElement("BUTTON");
        stop_button.innerHTML = "&#9995;"
        stop_button.setAttribute("class", "emoji-button")
        stop_button.id = "stop_container_button_id"
        stop_button.setAttribute("container-id", containers[i].getShortID().toString())
        container_row.insertCell().appendChild(stop_button)
        
        //if row is selected set selected class
        if(selected_id == containers[i].getShortID()){
          table.rows[i].setAttribute("class", "selected-tr")
        }

        //add event listeners
        //stop_button.addEventListener("click", event => this.onStopContainerButtonClick(event), true);
        log_button.addEventListener("click", event => this.onShowContainerLog(event), true);
      }
    }
  }

  onShowContainerLog(event)
  {
    let short_id = event.currentTarget.getAttribute("container-id")
    console.log("View:onShowContainerLog(" + short_id + ")")
    this.controller.fetchDockerLogs(short_id)
  }

  onModulesChanged()
  {
    //get data bases from model
    let modules = this.model.getModules()

    //get and clear devices table
    let table = document.getElementById('modules_table_id')

    if(modules.length == 0)
    {
      table.innerHTML = ""
      return
    }

    //create table header (if not already present)
    const header_labels = ["Ready", "Name", "Type", "Capture", "All", "Fixed", "Rate [Hz]", "Actions"]
    this.createTableHeader(table, header_labels)

    //get table body
    let table_body = table.querySelector('tbody')

    //delete unused rows
    let n = table_body.rows.length - modules.length
    for(let i = 0; i < n; i++) table_body.deleteRow(-1);

    //ready emojis
    const ready_emoji = "&#10004;"
    const not_ready_emoji = "&#9203;"

    //iterate devices
    for(let i = 0; i < modules.length; i++)
    {
      let m = modules[i]

      if(table_body.rows.length > i)
      {
        //use existing row
        table_body.rows[i].cells[0].innerHTML = m.getReady() ? ready_emoji : not_ready_emoji
        table_body.rows[i].cells[1].innerHTML = m.getName()
        table_body.rows[i].cells[2].innerHTML = m.getType()
        table_body.rows[i].cells[3].firstChild.checked = m.getCapture()
        table_body.rows[i].cells[3].firstChild.style.visibility = m.getCapturingAvailable() ? "visible" : "hidden";
        table_body.rows[i].cells[4].firstChild.checked = m.getAll()
        table_body.rows[i].cells[4].firstChild.style.visibility = m.getLiveAvailable() ? "visible" : "hidden";
        table_body.rows[i].cells[5].firstChild.checked = m.getFixed()
        table_body.rows[i].cells[5].firstChild.style.visibility = m.getLiveAvailable() ? "visible" : "hidden";
        table_body.rows[i].cells[6].firstChild.value = m.getFixedRate()
        table_body.rows[i].cells[6].firstChild.style.visibility = m.getLiveAvailable() ? "visible" : "hidden";

        let actions_cell = table_body.rows[i].cells[7]
        actions_cell.firstChild.innerHTML = ""
        this.createModuleButtons(m, actions_cell.firstChild)
        //table_body.rows[i].cells[6].firstChild.setAttribute("module-name", m.getName())
        //table_body.rows[i].cells[7].firstChild.setAttribute("module-name", m.getName())
        //table_body.rows[i].cells[8].firstChild.setAttribute("module-name", m.getName())
        const attr_indices = [3, 4, 5, 6]

        for(let k = 0; k < attr_indices.length; k++)
        {
          table_body.rows[i].cells[attr_indices[k]].firstChild.setAttribute("module-name", m.getName())
        }
      }
      else
      {
        //insert row
        let row = table_body.insertRow()

        //insert cells
        row.insertCell().innerHTML = m.getReady() ? ready_emoji : not_ready_emoji
        row.lastChild.style.fontSize = "24px"
        row.insertCell().innerHTML = m.getName()
        row.insertCell().innerHTML = m.getType()

        //capture checkbox
        let capture_checkbox = this.createCheckBox([['module-name', m.getName()]], m.getCapture())
        capture_checkbox.id = this.getNextFormIDString()
        capture_checkbox.style.visibility = m.getCapturingAvailable() ? "visible" : "hidden";
        capture_checkbox.addEventListener("click", event => this.onDataConfigChanged(event, "capture"), true);
        row.insertCell().appendChild(capture_checkbox)

        //live-all checkbox
        let all_checkbox = this.createCheckBox([['module-name', m.getName()]], m.getAll())
        all_checkbox.id = this.getNextFormIDString()
        all_checkbox.style.visibility = m.getLiveAvailable() ? "visible" : "hidden";
        all_checkbox.addEventListener("click", event => this.onDataConfigChanged(event, "all"), true);
        row.insertCell().appendChild(all_checkbox)

        //live-fixed checkbox
        let fixed_checkbox = this.createCheckBox([['module-name', m.getName()]], m.getFixed())
        fixed_checkbox.id = this.getNextFormIDString()
        fixed_checkbox.style.visibility = m.getLiveAvailable() ? "visible" : "hidden";
        fixed_checkbox.addEventListener("click", event => this.onDataConfigChanged(event, "fixed"), true);
        row.insertCell().appendChild(fixed_checkbox)

        //live-fixed period form
        let fixed_rate_form = document.createElement("INPUT");
        fixed_rate_form.id = this.getNextFormIDString()
        fixed_rate_form.setAttribute("type", "number");
        fixed_rate_form.setAttribute("class", "table-input-form");
        fixed_rate_form.setAttribute("module-name", m.getName())
        fixed_rate_form.value = m.getFixedRate()
        fixed_rate_form.style.visibility = m.getLiveAvailable() ? "visible" : "hidden";
        fixed_rate_form.addEventListener("change", event => this.onDataConfigChanged(event, "rate"), true);
        row.insertCell().appendChild(fixed_rate_form)

        //module buttons
        let actions_div = document.createElement("div")
        actions_div.className = "module-buttons-div"
        let actions_cell = row.insertCell()
        actions_cell.style.maxWidth = "300px"
        actions_cell.appendChild(actions_div)

        //create module buttons
        this.createModuleButtons(m, actions_div)
      }

      //highlight selected row
      let row_class = m.getName() == this.model.getSelectedModule() ? "selected-tr" : "tr"
      table.rows[i].setAttribute("class", row_class)
    } 
  }

  createModuleButtons(m, parent_div)
  {
    //create show config button
    let show_config_button = this.createEmojiButtonWithLabel(parent_div, [['module-name', m.getName()]], "&#128269;", "Config")
    show_config_button.addEventListener("click", event => this.onGetConfig(event), true);

    //create show preview button
    let preview_button = this.createEmojiButtonWithLabel(parent_div, [['module-name', m.getName()]], "&#128161;", "Preview")
    preview_button.addEventListener("click", event => this.onGetPreview(event), true);

    //create show documentation button
    let doc_button = this.createEmojiButtonWithLabel(parent_div, [['module-name', m.getName()]], "&#128196;", "Doc")
    doc_button.addEventListener("click", event => this.onGetDocumentation(event), true);
    
    let webinterfaces_list = m.getWebInterfacesList()

    for(let i = 0; i < webinterfaces_list.length; i++)
    {
      let label = webinterfaces_list[i]['label']
      let port = webinterfaces_list[i]['port']
      let databeam_ip = this.model.getDataBeamIP() + ":" + port.toString()
      let web_button = this.createEmojiButtonWithLabel(parent_div, [['module-name', m.getName()]], "&#127760;", label)
      web_button.setAttribute("m-url", databeam_ip)
      web_button.addEventListener("click", event => this.onOpenModuleWebInterface(event), true);
    }

    let video_streams_list = m.getVideoStreamsList()

    for(let i = 0; i < video_streams_list.length; i++)
    {
      let label = video_streams_list[i]['label']
      let stream_port = video_streams_list[i]['port']
      let stream_path = video_streams_list[i]['path']
      let stream_url = this.model.getDataBeamIP() + ":" + stream_port + stream_path
      let stream_button = this.createEmojiButtonWithLabel(parent_div, [['module-name', m.getName()]], "&#127909;", label)
      stream_button.setAttribute("m-url", stream_url)
      stream_button.addEventListener("click", event => this.onOpenModuleWebInterface(event), true);
    }
  }

  createEmojiButtonWithLabel(parent_div, attributes, emoji_str, label_str)
  {
    let emoji_button = this.createEmojiButton(attributes, emoji_str)

    let label_div = document.createElement("div")
    label_div.innerHTML = label_str
    label_div.className = "emoji-button-label"

    let button_div = document.createElement("div")
    button_div.className = "emoji-button-div"
    button_div.appendChild(emoji_button)
    button_div.appendChild(label_div)
    parent_div.appendChild(button_div)

    return emoji_button
  }

  onDataConfigChanged(event, key)
  {
    //get module name and data config dict of module
    let module_name = event.currentTarget.getAttribute("module-name")
    let data_config = this.model.getModuleByName(module_name).getDataConfigDict()

    //update data config field
    if(key == "capture") data_config.enable_capturing = event.currentTarget.checked
    if(key == "all") data_config.enable_live_all_samples = event.currentTarget.checked
    if(key == "fixed") data_config.enable_live_fixed_rate = event.currentTarget.checked
    if(key == "rate") data_config.live_rate_hz = Math.min(Math.max(parseFloat(event.currentTarget.value), 0.1), 100.0)

    //send new data config
    this.controller.updateDataConfig(module_name, data_config)
  }

  onGetConfig(event)
  {
    console.log("View:onGetConfig()")
    document.getElementById("config_div_id").style.display = "flex"
    document.getElementById("documentation_div_id").style.display = "none"
    document.getElementById("preview_div_id").style.display = "none"
    this.controller.fetchConfig(event.currentTarget.getAttribute("module-name"))
  }

  onGetDocumentation(event)
  {
    console.log("View:onGetConfig()")
    document.getElementById("config_div_id").style.display = "none"
    document.getElementById("documentation_div_id").style.display = "flex"
    document.getElementById("preview_div_id").style.display = "none"
    this.controller.fetchDocumentation(event.currentTarget.getAttribute("module-name"))
  }

  onOpenModuleWebInterface(event)
  {
    let url = event.currentTarget.getAttribute("m-url")
    console.log("onOpenModuleWebInterface; " + url)
    window.open(url, "_blank")
  }

  onGetPreview(event)
  {
    console.log("View:onGetConfig()")
    document.getElementById("config_div_id").style.display = "none"
    document.getElementById("documentation_div_id").style.display = "none"
    document.getElementById("preview_div_id").style.display = "flex"

    // get and clear preview select
    let preview_select = document.getElementById("preview_topic_id")
    preview_select.innerHTML = ""

    // get module mcap topics
    let module_name = event.currentTarget.getAttribute("module-name")
    let module = this.model.getModuleByName(module_name)
    
    // fill select with module topics and select current selected schema index
    if(module != undefined)
    {
      let mcap_topics = module.getMCAPTopics()
      let selected_schema_index = module.getLatestSchemaIndex()

      mcap_topics.forEach((topic, index) => {
        let option = document.createElement("option");
        option.text = topic
        if(index == selected_schema_index) option.selected = true
        preview_select.add(option)
      })
    }

    this.controller.requestPreview(module_name)
  }

  onPreviewTopicSelectionChanged(event)
  {
    //get latest topic string
    let latest_topic = event.currentTarget.value

    //set latest topic for selected module
    this.model.setLatestTopic(latest_topic)

    //request preview for selected topic
    this.controller.requestPreview(this.model.getSelectedModule())
  }

  onDocumentationChanged()
  {
    //get and clear module documentation div
    let module_doc_div = document.getElementById("module_doc_div_id")
    module_doc_div.innerHTML = ""
    
    //get selected module
    let module = this.model.getModuleByName(this.model.getSelectedModule())

    //append mcap topics list if present
    if(module != undefined && module.hasMCAPTopics())
    {
      //create header
      let header = document.createElement("h2")
      header.innerHTML = "MCAP Topics"
      module_doc_div.appendChild(header)

      //create list element
      let ul = document.createElement("ul")

      //get module mcap topics
      let mcap_topics = module.getMCAPTopics()

      //append topics to list
      mcap_topics.forEach(topic => {
        let li = document.createElement("li")
        li.textContent = topic
        ul.appendChild(li)
      })

      //append topics list to documentation div
      module_doc_div.appendChild(ul)
    }

    //append module documentation
    let documentation_div = document.createElement("div")
    documentation_div.innerHTML = this.model.getModuleDocumentation()
    module_doc_div.appendChild(documentation_div)
  }

  onPreviewDataChanged()
  {
    //get preview data
    let preview_data = this.model.getPreviewData()

    //get and clear devices table
    let table = document.getElementById('preview_table_id')

    //get preview header id
    let preview_header = document.getElementById('preview_header_id')

    //create table and return if there is no preview data
    if(preview_data == undefined)
    {
      table.innerHTML = ""
      preview_header.innerHTML = "Preview"
      return
    }

    //include module name in preview header
    preview_header.innerHTML = "Preview: " + this.model.getSelectedModule()

    //check if this preview data is an image
    if(preview_data.hasOwnProperty("format"))
    {
      document.getElementById("preview_table_div_id").style.display = "none"
      let prev_image_div = document.getElementById("preview_img_div_id")
      prev_image_div.style.display = "block"
      prev_image_div.innerHTML = ""
      let preview_image = new Image(preview_data['res_x'], preview_data['res_y'])
      preview_image.src = "data:image/jpeg;base64," + preview_data['data']
      preview_image.setAttribute("class","preview-image")
      prev_image_div.appendChild(preview_image)
      return
    }

    //this preview data contains numerical data
    document.getElementById("preview_table_div_id").style.display = "block"
    document.getElementById("preview_img_div_id").style.display = "none"

    //holds list of keys and values
    let preview_list = []

    //create list of keys and values
    for(const [key, value] of Object.entries(preview_data))
    {
      preview_list.push([key, value])
    }

    //sort by keys, ts is always first
    preview_list.sort((a, b) => a[0] == "ts" ? -1 : (a[0] < b[0] ? -1 : 1))

    //create table header
    const header_labels = ["Key", "Value"]
    const header_styles = [{'width': '50%'}, {'width': '50%'}]
    this.createTableHeader(table, header_labels, header_styles)

    //get table body
    let table_body = table.querySelector('tbody')

    //delete unused rows
    let n = table_body.rows.length - preview_list.length
    for(let i = 0; i < n; i++) table_body.deleteRow(-1);

    //iterate devices
    for(let i = 0; i < preview_list.length; i++)
    {
      let key = preview_list[i][0]
      let value = preview_list[i][1]

      if(table_body.rows.length > i)
      {
        //use existing row
        table_body.rows[i].cells[0].innerHTML = key
        table_body.rows[i].cells[1].innerHTML = value
      }
      else
      {
        //insert row
        let row = table_body.insertRow()
        row.insertCell().innerHTML = key
        row.insertCell().innerHTML = value
      }
    }
  }

  onMeasurementsChanged()
  {
    //get data bases from model
    let measurements = this.model.getMeasurements()

    //get and clear devices table
    let table = document.getElementById('measurements_table_id')

    //clear table and return if there are no measurements
    if(measurements.length == 0)
    {
      table.innerHTML = ""
      let dl_button = document.getElementById("download_measurements_button_id")
      let rm_button = document.getElementById("remove_measurenemts_button_id")
      dl_button.innerHTML = "Download"
      rm_button.innerHTML = "Remove"
      dl_button.disabled = true
      rm_button.disabled = true
      return
    }

    //create table header
    if(table.querySelector('thead') == null)
    {
      let header_checkbox = this.createCheckBox([], false)
      header_checkbox.id = this.getNextFormIDString()
      header_checkbox.addEventListener("click", event => this.onMeasurementHeaderCheckbox(event), true);
      const header_styles = [{}, {}, {}, {}, {}, {}, {}, {}, {}]
      const header_labels = [header_checkbox, "Date", "Run Tag", "Run ID", "Duration", "Total Size", "Modules", "Download", "Remove"]
      this.createTableHeader(table, header_labels, header_styles)
    }

    //get table body
    let table_body = table.querySelector('tbody')

    //delete unused rows
    let n = table_body.rows.length - measurements.length
    for(let i = 0; i < n; i++) table_body.deleteRow(-1);

    //counts number of selected measurements
    let num_selected = 0
    let selected_byte_count = 0

    let capture = this.model.getCaptureRunning()

    //iterate devices
    for(let i = 0; i < measurements.length; i++)
    {
      //get current measurement
      let m = measurements[i]
      let unfinished = m.getDuration() == ""
      num_selected += m.getSelected() ? 1 : 0
      selected_byte_count += m.getSelected() ? m.getTotalSizeBytes() : 0

      if(table_body.rows.length > i)
      {
        //use existing row
        table_body.rows[i].cells[0].firstChild.setAttribute("measurement-name", m.getName())
        table_body.rows[i].cells[0].firstChild.checked = m.getSelected()
        table_body.rows[i].cells[1].innerHTML = m.getDisplayName()
        table_body.rows[i].cells[2].innerHTML = m.getRunTag()
        table_body.rows[i].cells[3].innerHTML = m.getRunID()
        table_body.rows[i].cells[4].innerHTML = unfinished ? "&#128192;" : m.getDisplayDuration()
        table_body.rows[i].cells[5].innerHTML = Util.ByteCountToString(m.getTotalSizeBytes())
        table_body.rows[i].cells[6].innerHTML = m.getDisplayModules()
        table_body.rows[i].cells[7].firstChild.href = this.model.getDataBeamURLHTTP() + "/download/measurement/" + m.getName();
        table_body.rows[i].cells[7].firstChild.download = m.getName() + ".zip"
        table_body.rows[i].cells[7].firstChild.firstChild.disabled = unfinished && capture
        table_body.rows[i].cells[8].firstChild.setAttribute("measurement-name", m.getName())
        table_body.rows[i].cells[8].firstChild.disabled = unfinished && capture
      }
      else
      {
        //insert row
        let row = table_body.insertRow()

        //select checkbox
        let checkbox = this.createCheckBox([["measurement-name", m.getName()]], m.getSelected())
        checkbox.id = this.getNextFormIDString()
        checkbox.addEventListener("click", event => this.onMeasurementCheckboxClick(event), true);

        //insert cells
        row.insertCell().appendChild(checkbox)
        row.insertCell().innerHTML = m.getDisplayName()

        row.lastChild.style.whiteSpace = "nowrap"

        row.insertCell().innerHTML = m.getRunTag()

        // prevent too long run tag cells
        row.lastChild.style.maxWidth = "20ch"

        row.insertCell().innerHTML = m.getRunID()
        row.insertCell().innerHTML = unfinished ? "&#128192;" : m.getDisplayDuration()
        row.insertCell().innerHTML = Util.ByteCountToString(m.getTotalSizeBytes())
        row.insertCell().innerHTML = m.getDisplayModules()

        // prevent too long modules cells
        row.lastChild.style.maxWidth = "30ch"

        //create download link
        let a = document.createElement("a");
        a.href = this.model.getDataBeamURLHTTP() + "/download/measurement/" + m.getName();
        a.download = m.getName() + ".zip"
        row.insertCell().appendChild(a);

        //download measurement button
        var download_button = this.createEmojiButton([], "&#128190;")
        download_button.disabled = unfinished && capture
        a.appendChild(download_button)

        //create remove meta entry icon
        let remove_button = this.createEmojiButton([["measurement-name", m.getName()]], "&#128293;")
        remove_button.addEventListener("click", event => this.onRemoveFile(event));
        remove_button.disabled = unfinished && capture
        row.insertCell().appendChild(remove_button)
      }
    }

    //compute names for download and remove buttons
    let str = ""
    let byte_str = Util.ByteCountToString(selected_byte_count)
    if(num_selected > 0 && num_selected == measurements.length) str = " (All, " + byte_str + ")"
    if(num_selected == 1) str = " (1, " + byte_str + ")"
    if(num_selected > 1 && num_selected < measurements.length) str = " (" + num_selected.toString() + ", " + byte_str +  ")"

    //set button names and disabled flags
    let dl_button = document.getElementById("download_measurements_button_id")
    let rm_button = document.getElementById("remove_measurenemts_button_id")
    dl_button.innerHTML = "Download" + str
    rm_button.innerHTML = "Remove" + str
    dl_button.disabled = num_selected == 0
    rm_button.disabled = num_selected == 0

    let data_actions_div = document.getElementById("data_actions_div_id")
    data_actions_div.style.display = num_selected == 0 ? "none" : "flex"
  }

  onMeasurementHeaderCheckbox(event)
  {
    this.model.setAllMeasurementsSelected(event.currentTarget.checked)
  }

  onMeasurementCheckboxClick(event)
  {
    let measurement_name = event.currentTarget.getAttribute("measurement-name")
    let checked = event.currentTarget.checked
    this.model.setMeasurementSelected(measurement_name, checked)
    console.log("Measurement checkbox: " + measurement_name + " " + checked.toString())
  }

  onConfigChanged()
  {
    console.log("View:onModelConfigInspectorChanged()")

    let config_module_name = this.model.getConfigModuleName()

    if(config_module_name == "")
    {
      document.getElementById("config_div_id").style.display = "none"
      return
    }
    else
    {
      document.getElementById("config_div_id").style.display = "flex"
    }

    //highlight apply button if config is dirty
    let apply_config_button = document.getElementById("apply_config_button_id")
    apply_config_button.style.background = this.model.getConfigDirty() ? "#fcba03" : ""

    //update plain text config
    let config_text_area = document.getElementById('config_inspector_id')
    config_text_area.value = this.model.getConfig()

    //get and clear forms div
    let forms_div = document.getElementById('forms_config_div_id')

    //store current scroll position
    let scroll_top_save = forms_div.scrollTop

    //clear forms div
    forms_div.innerHTML = ""

    //get config entries
    //let config_entries = this.model.getConfigEntries()
    let config_entries = this.model.getRootConfigEntry().getEntryList()

    //create config forms
    this.createConfigForms(forms_div, config_entries)

    //restore scroll position
    forms_div.scrollTop = scroll_top_save
  }

  createConfigForms(forms_div, config_entries)
  {
    let nowrap = this.model.getConfigLayout() == "nowrap"

    //interate config entries
    for(let i = 0; i < config_entries.length; i++)
    {
      //get current entry
      let entry = config_entries[i]

      //skip if not visible
      if(entry.getVisible() == false || entry.getHiddenFlag()) continue

      //create entry div
      let entry_div = document.createElement("div")
      entry_div.setAttribute("class", "config-entry-div")
      if(entry.getIndent() > 0) entry_div.style.marginLeft = entry.getIndent().toString() + "px"

      let heading = document.createElement("p")
      heading.setAttribute("class", "config-label")
      heading.innerHTML = entry.getPrettyLabel()
      let heading_button = undefined
      //forms_div.appendChild(heading)
      if(entry.getType() == "object")
      {
        heading.style.color = "dodgerblue"
        let heading_row = document.createElement("div")
        heading_row.setAttribute("class", "config-header-row")
        heading_row.appendChild(heading)
        heading_button = document.createElement("BUTTON");
        heading_button.innerHTML = "&#128317;"
        heading_button.className = "config-object-button"
        heading_row.appendChild(heading_button)
        //heading.addEventListener(
        //  "click", event => this.onConfigObjectClick(event, entry.getMember()), true);
        entry_div.appendChild(heading_row)
      }
      else
      {
        entry_div.appendChild(heading)
      }
      

      if(entry.isArray())
      {
        let array = entry.getArray()

        if(entry.getType() == "object")
        {
          let info_div = document.createElement("p")
          info_div.setAttribute("class", "config-not-supported-p")
          info_div.innerHTML = "Object arrays are currently not supported, use advanced config " +
            "editing instead."
            entry_div.appendChild(info_div)
          continue
        }

        // get max digits for all array entries
        let max_digits = entry.getMaxArrayEntryDigits()

        let elements_div = document.createElement("div")
        elements_div.className = "cfg-array"
        if(nowrap) elements_div.style.flexWrap = "nowrap" 
        if(nowrap) elements_div.style.flexDirection = "column" 
        if(array.length > 0) entry_div.appendChild(elements_div)

        for(let j = 0; j < array.length; j++)
        {
          //create input
          let input = document.createElement("INPUT")
          input.setAttribute("class", "config-form")
          input.setAttribute("config-index", entry.getIndex().toString())
          input.setAttribute("array-index", j.toString())
          input.id = this.getNextFormIDString()

          //create label div
          let label = document.createElement("div")
          label.className = "cfg-array-label"
          label.innerHTML = j.toString() + ":";

          //create item div (label + input)
          let item_div = document.createElement("div")
          item_div.className = "cfg-array-item"
          item_div.appendChild(label)
          elements_div.appendChild(item_div);

          if(entry.getType() == "string")
          {
            if(entry.getDisplayType() == "select")
            {
              //create fill method select dropdown
              let select = document.createElement("SELECT");
              select.setAttribute("config-index", entry.getIndex().toString())
              select.setAttribute("array-index", j.toString())
              select.id = this.getNextFormIDString()

              //define available fill options
              let fill_options = entry.getProperties()["options"]

              //add fill options to select drop down
              for(let k = 0; k < fill_options.length; k++)
              {
                let option = document.createElement("option");
                //option.setAttribute("class", "measurement-option")
                if(entry.getArrayValue(j) == fill_options[k]) option.selected = true
                option.text = fill_options[k]
                select.add(option);
              }

              select.addEventListener("change", event => this.onSubmitConfigInputText(event), true);
              item_div.appendChild(select)
            }
            else
            {
              input.setAttribute("type", "text")
              input.value = array[j]
              input.addEventListener("submit", event => this.onSubmitConfigInputText(event), true);
              input.addEventListener("change", event => this.onSubmitConfigInputText(event), true);
              if(!nowrap) item_div.style.flex = "1 1 " + (max_digits + 4).toString() + "ch"
              item_div.appendChild(input)
            }
          }

          if(entry.getType() == "number")
          {
            input.setAttribute("type", "number")
            input.value = array[j]
            input.addEventListener("submit", event => this.onSubmitConfigInputNumber(event), true);
            input.addEventListener("change", event => this.onSubmitConfigInputNumber(event), true);
            if(!nowrap) item_div.style.flex = "1 1 " + (max_digits + 4).toString() + "ch"
            item_div.appendChild(input)
          }

          if(entry.getType() == "boolean")
          {
            input.setAttribute("type", "checkbox")
            input.checked = array[j]
            input.addEventListener("click", event => this.onSubmitConfigInputChecked(event), true);
            if(!nowrap) item_div.style.width = "7ch"
            if(!nowrap) item_div.style.justifyContent = "end"
            item_div.appendChild(input)
          }
        }

        if(array.length == 0)
        {
            let array_buttons_div = document.createElement("div")
            array_buttons_div.setAttribute("class", "cfg-array-buttons")
            entry_div.appendChild(array_buttons_div)

            var init_string_button = document.createElement("BUTTON");
            init_string_button.innerHTML = "+ string"
            init_string_button.className = "config-array-buttons"
            init_string_button.setAttribute("config-index", entry.getIndex().toString())
            init_string_button.setAttribute("config-array-type", "string")
            init_string_button.addEventListener("click", event => this.onSubmitInitConfigArray(event), true);
            array_buttons_div.appendChild(init_string_button)

            var init_number_button = document.createElement("BUTTON");
            init_number_button.innerHTML = "+ number"
            init_number_button.className = "config-array-buttons"
            init_number_button.setAttribute("config-index", entry.getIndex().toString())
            init_number_button.setAttribute("config-array-type", "number")
            init_number_button.addEventListener("click", event => this.onSubmitInitConfigArray(event), true);
            array_buttons_div.appendChild(init_number_button)

            var init_boolean_button = document.createElement("BUTTON");
            init_boolean_button.innerHTML = "+ boolean"
            init_boolean_button.className = "config-array-buttons"
            init_boolean_button.setAttribute("config-index", entry.getIndex().toString())
            init_boolean_button.setAttribute("config-array-type", "boolean")
            init_boolean_button.addEventListener("click", event => this.onSubmitInitConfigArray(event), true);
            array_buttons_div.appendChild(init_boolean_button)
        }
        else
        {
          if(entry.hasPropertyFlag("resizeable"))
          {
            let array_buttons_div = document.createElement("div")
            array_buttons_div.setAttribute("class", "cfg-array-buttons")
            entry_div.appendChild(array_buttons_div)

            var add_array_button = document.createElement("BUTTON");
            add_array_button.innerHTML = "+"
            add_array_button.className = "config-array-buttons"
            add_array_button.setAttribute("config-index", entry.getIndex().toString())
            add_array_button.addEventListener("click", event => this.onSubmitAddConfigArray(event), true);

            var sub_array_button = document.createElement("BUTTON");
            sub_array_button.innerHTML = "-"
            sub_array_button.className = "config-array-buttons"
            sub_array_button.setAttribute("config-index", entry.getIndex().toString())
            sub_array_button.addEventListener("click", event => this.onSubmitSubConfigArray(event), true);

            array_buttons_div.appendChild(sub_array_button)
            array_buttons_div.appendChild(add_array_button)
          }
        }
      }
      else
      {
        if(entry.getDisplayType() == "select")
        {
          //create fill method select dropdown
          let select = document.createElement("SELECT");
          select.id = this.getNextFormIDString()
          select.setAttribute("config-index", entry.getIndex().toString())

          //define available fill options
          let fill_options = entry.getProperties()["options"]

          //add fill options to select drop down
          for(let j = 0; j < fill_options.length; j++)
          {
            let option = document.createElement("option");
            //option.setAttribute("class", "measurement-option")
            if(entry.getValue() == fill_options[j]) option.selected = true
            option.text = fill_options[j]
            select.add(option);
          }

          select.addEventListener("change", event => this.onSubmitConfigInputSelect(event), true);
          entry_div.appendChild(select)
        }
        else
        {
          let input = document.createElement("INPUT")
          input.id = this.getNextFormIDString()
          input.setAttribute("class", "config-form")
          input.setAttribute("config-index", entry.getIndex().toString())

          if(entry.getType() == "string")
          {
            if(entry.hasPropertyFlag("button"))
            {
              let config_button = document.createElement("BUTTON");
              config_button.innerHTML = entry.getValue()
              config_button.className = "config-buttons"
              config_button.addEventListener(
                "click", event => this.onConfigButtonClick(event, entry.getMember()), true);
              entry_div.appendChild(config_button)
            }
            else
            {
              input.setAttribute("type", "text")
              input.value = entry.getValue()
              input.addEventListener("submit", event => this.onSubmitConfigInputText(event), true);
              input.addEventListener("change", event => this.onSubmitConfigInputText(event), true);
              entry_div.appendChild(input)
            }
          }

          if(entry.getType() == "number")
          {
            input.setAttribute("type", "number")
            input.value = entry.getValue()
            input.addEventListener("submit", event => this.onSubmitConfigInputNumber(event), true);
            input.addEventListener("change", event => this.onSubmitConfigInputNumber(event), true);
            entry_div.appendChild(input)
          }

          if(entry.getType() == "boolean")
          {
            input.setAttribute("type", "checkbox")
            input.checked = entry.getValue()
            input.addEventListener("click", event => this.onSubmitConfigInputChecked(event), true);

            let elements_div = document.createElement("div")
            elements_div.setAttribute("class", "config-forms-horizontal")
            elements_div.appendChild(input);
            entry_div.appendChild(elements_div)
          }

          if(entry.getType() == "object")
          {
            //create entry div
            let sub_entry_div = document.createElement("div")
            sub_entry_div.id = "sub_cfg_" + entry.getIndex().toString()
            sub_entry_div.setAttribute("class", "cfg-object")
            sub_entry_div.style.marginLeft = "20px"
            sub_entry_div.style.display = entry.getSubVisible() ? "flex" : "none"
            entry_div.appendChild(sub_entry_div)

            heading_button.setAttribute("sub-div-id", sub_entry_div.id)
            heading_button.addEventListener("click", event => this.onConfigToggleObjectDiv(event), true);
            heading_button.setAttribute("config-index", entry.getIndex().toString())

            //console.log(`Skip Config Entry of type object with key ${entry.getPrettyLabel()}`)
            this.createConfigForms(sub_entry_div, entry.getEntryList())
          }
        }
      }

      //append entry div to config forms div
      forms_div.appendChild(entry_div)
    }

    //restore scroll position
    //forms_div.scrollTop = scroll_top_save
  }

  onConfigToggleObjectDiv(event)
  {
    let sub_div_id = event.currentTarget.getAttribute("sub-div-id")
    let config_index = event.currentTarget.getAttribute("config-index")
    let sub_div = document.getElementById(sub_div_id)
    sub_div.style.display = sub_div.style.display == "flex" ? "none" : "flex"

    this.model.updateConfigEntry(config_index, -1, sub_div.style.display == "flex")
  }

  onSubmitAddConfigArray(event)
  {
    console.log("View:onSubmitAddConfigArray()")
    let config_index = parseInt(event.currentTarget.getAttribute("config-index"))
    this.model.pushConfigArrayEntry(config_index)
  }

  onSubmitSubConfigArray(event)
  {
    console.log("View:onSubmitSubConfigArray()")
    let config_index = parseInt(event.currentTarget.getAttribute("config-index"))
    this.model.popConfigArrayEntry(config_index)
  }

  onSubmitInitConfigArray(event)
  {
    console.log("View:onSubmitInitConfigArray()")
    let config_index = parseInt(event.currentTarget.getAttribute("config-index"))
    let config_array_type = event.currentTarget.getAttribute("config-array-type")
    this.model.initConfigArrayType(config_index, config_array_type)
  }

  onSubmitConfigInputText(event)
  {
    console.log("View:onSubmitConfigInputText()")
    let config_index = parseInt(event.currentTarget.getAttribute("config-index"))

    if(event.currentTarget.hasAttribute("array-index"))
    {
      let array_index = parseInt(event.currentTarget.getAttribute("array-index"))
      this.model.updateConfigEntry(config_index, array_index, event.currentTarget.value)
    }
    else
    {
      this.model.updateConfigEntry(config_index, -1, event.currentTarget.value)
    }
  }

  onSubmitConfigInputSelect(event)
  {
    console.log("View:onSubmitConfigInputSelect()")
    let config_index = parseInt(event.currentTarget.getAttribute("config-index"))
    this.model.updateConfigEntry(config_index, -1, event.currentTarget.value)
  }

  onSubmitConfigInputNumber(event)
  {
    console.log("View:onSubmitConfigInputNumber()")

    let value = parseFloat(event.currentTarget.value)

    if(isNaN(value))
    {
      value = 0
      event.currentTarget.value = "0"
    }

    let config_index = parseInt(event.currentTarget.getAttribute("config-index"))

    if(event.currentTarget.hasAttribute("array-index")){
      let array_index = parseInt(event.currentTarget.getAttribute("array-index"))
      this.model.updateConfigEntry(config_index, array_index, value)
    }
    else{
      this.model.updateConfigEntry(config_index, -1, value)
    }
  }

  onSubmitConfigInputChecked(event)
  {
    console.log("View:onSubmitConfigInputChecked()")
    let config_index = parseInt(event.currentTarget.getAttribute("config-index"))

    if(event.currentTarget.hasAttribute("array-index")){
      let array_index = parseInt(event.currentTarget.getAttribute("array-index"))
      this.model.updateConfigEntry(config_index, array_index, (event.currentTarget.checked))
    }
    else{
      this.model.updateConfigEntry(config_index, -1, (event.currentTarget.checked))
    }
  }

  onConfigButtonClick(event, config_key)
  {
    console.log("Config button click: " + config_key)
    this.controller.onPostConfigButtonClick(config_key)
  }

  onConfigLayoutButtonClick(event)
  {
    this.model.toggleConfigLayout()
    this.updateConfigLayoutButton()
  }

  updateConfigLayoutButton()
  {
    //toggle emoji
    let button = document.getElementById("config_layout_button_id")
    button.innerHTML = this.model.getConfigLayout() == "nowrap" ? "&#128203;" : "&#128230;"
  }

  onSimpleConfigButtonClick(event)
  {
    console.log("View::onSimpleConfigButtonClick()")
    document.getElementById("forms_config_div_id").style.display = "flex";
    document.getElementById("config_inspector_id").style.display = "none";
    let shadow = '0px 0px 2px 2px var(--heading_color) inset'
    document.getElementById('simple_config_button_id').style.boxShadow = shadow
    document.getElementById('advanced_config_button_id').style.boxShadow = ''
    document.getElementById("config_layout_button_id").style.display = ""
  }

  onAdvancedConfigButtonClick(event)
  {
    console.log("View::onAdvancedConfigButtonClick()")
    document.getElementById("forms_config_div_id").style.display = "none";
    document.getElementById("config_inspector_id").style.display = "block";
    let shadow = '0px 0px 2px 2px var(--heading_color) inset'
    document.getElementById('simple_config_button_id').style.boxShadow = ''
    document.getElementById('advanced_config_button_id').style.boxShadow = shadow
    document.getElementById("config_layout_button_id").style.display = "none"
  }

  onApplyConfigButtonClick(event)
  {
    console.log("View:onApplyConfigButtonClick()")
    let config_str = document.getElementById('config_inspector_id').value
    this.controller.onAppyConfig(config_str)
  }

  onStoreConfigButtonClick(event)
  {
    console.log("View:onStoreConfigButtonClick()")
    let config_str = document.getElementById('config_inspector_id').value
    this.controller.onStoreConfig(config_str)
  }

  onLoadConfigButtonClick(event)
  {
    console.log("View:onLoadConfigButtonClick()")
    let file_upload_input = document.getElementById("load_config_file_id")
    file_upload_input.click()
  }

  onLoadConfigFileChanged(event)
  {
    console.log("View:onLoadConfigFileChanged()")
    let file_upload_input = document.getElementById("load_config_file_id")
    this.controller.onLoadConfigFileChanged(file_upload_input.files[0])
  }

  onDefaultConfigButtonClick(event)
  {
    console.log("View:onDefaultConfigButtonClick()")
    this.controller.onDefaultConfig()
  }

  onConfigTextAreaChanged(event)
  {
    console.log("View:onConfigTextAreaChanged()")
    let config_str = document.getElementById('config_inspector_id').value
    this.model.updateConfig(config_str, true)
  }

  onRemoveFile(event)
  {
    let measurement_name = event.currentTarget.getAttribute("measurement-name")

    let self = this

    this.customConfirm("Remove Measurement", "Do you really want to remove measurement \"" + 
      measurement_name + "\" ?",
      () => {
        console.log("Remove Measurement: " + measurement_name)
        self.controller.removeMeasurement([measurement_name])
      })
  }

  onRemoveMeasurements(event)
  {
    let self = this

    this.customConfirm("Remove Measurements", "Do you really want to remove selected measurements?",
      () => {
        console.log("Remove selected measurements.")
        self.controller.removeSelectedMeasurements()
      })
  }

  onDownloadMeasurements(event)
  {
    this.controller.downloadSelectedMeasurements()
  }

  onThemeSelectChanged(event)
  {
    console.log("onThemeSelectChanged(" + event.currentTarget.value + ")")
    this.model.setTheme(event.currentTarget.value)
  }

  onModelThemeChanged()
  {
    console.log("onModelThemeChanged()")
    let theme = this.model.getTheme()
    document.documentElement.setAttribute('theme', theme);
    document.getElementById("theme_select_id").value = theme;

    if(theme == "Dark"){
      document.getElementById("db_header_logo_img").src = "../static/images/databeam-logo-small-white.png"
    }
    else{
      document.getElementById("db_header_logo_img").src = "../static/images/db_logo_1.png"
    }
  }

  getNextFormIDString()
  {
    this.form_id_counter += 1
    return "form-" + this.form_id_counter.toString()
  }
}
