
class TablePlot extends Plot
{
  constructor(plot_div, legend_div, options_div, plot_options)
  {
    super();
    this.plot_div = plot_div
    this.legend_div = legend_div
    this.options_div = options_div

    this.table = document.createElement("table")
    this.table.setAttribute("class", "measurement-table")
    this.plot_div.appendChild(this.table)
  }

  plot(keys, values, module_changed)
  {
    //get table as local variable
    let table = this.table

    //create table if rows do not match
    if(table.rows.length != (keys.length + 1))
    {
      table.innerHTML = ""
      let thead = document.createElement("thead");
      table.appendChild(thead)
      let header_row = thead.insertRow()
      let column_th = document.createElement("th")
      let value_th = document.createElement("th")
      column_th.innerHTML = "Key"
      column_th.style.width = "30%"
      value_th.innerHTML = "Value"
      header_row.appendChild(column_th)
      header_row.appendChild(value_th)

      let tbody = document.createElement("tbody");

      for(let i = 0; i < keys.length; i++)
      {
        let row = tbody.insertRow()
        row.insertCell().innerHTML = ""
        let value_row = row.insertCell()
        value_row.innerHTML = ""
        value_row.style.wordBreak = "break-word"
      }

      table.appendChild(tbody)
    }

    //update table data
    for(let i = 0; i < keys.length; i++)
    {
      let row = table.rows[i + 1]

      row.cells[0].innerHTML = keys[i]

      if(typeof(values[i]) != "object" )
      {
        row.cells[1].innerHTML = values[i]
      }
      else if(Array.isArray(values[i]))
      {
        row.cells[1].innerHTML = "array [" + values[i].length.toString() + "]";
      }
    }
  }

  reset()
  {
    this.table.innerHTML = ""
  }
}