class ConfigEntry
{
  constructor()
  {
    this.parent = null
    this.member = ""
    this.type = "string"
    this.label = "label"
    this.label_pretty = "Label"
    this.properties = undefined
    this.display_type = ""
    this.visible = true
    this.visible_str = ""
    this.indent = 0
    this.hidden_flag = false
  }

  isArray(){ return Array.isArray(this.parent) }
  getArray(){ return this.parent }
  getType(){ return this.type }
  getLabel(){ return this.label }
  getMember() { return this.member}
  getPrettyLabel() { return this.label_pretty }
  getValue() { return this.parent[this.member] }
  getArrayValue(index) { return this.parent[index]}
  hasProperties(){ return this.properties != undefined}
  getProperties(){return this.properties}
  setDisplayType(display_type){this.display_type = display_type}
  getDisplayType(){return this.display_type}
  setVisible(visible) { this.visible = visible}
  getVisible(){ return this.visible }
  getIndent(){ return this.indent }
  getHiddenFlag() { return this.hidden_flag }

  hasPropertyFlag(flag)
  {
    if(this.properties == undefined) return false;
    if(!("flags" in this.properties)) return false;
    return this.properties["flags"].includes(flag)
  }

  Set(parent, member, type, label) 
  {
    //console.log("Parent: " + parent + " member: " + member + " type: " + type + " label: " + label)

    this.parent = parent
    this.member = member
    this.type = type
    this.label = label

    this.label_pretty = label
    this.label_pretty = this.label_pretty.split("_").join(" ")
    this.label_pretty = this.label_pretty.split("-").join(" ")

    for(let i = 0; i < this.label_pretty.length; i++)
    {
      if(i == 0)
      {
        this.label_pretty = this.replaceChar(this.label_pretty, this.label_pretty[i].toUpperCase(), 0)
        continue
      }

      if(this.label_pretty[i-1] == ' ')
      {
        this.label_pretty = this.replaceChar(this.label_pretty, this.label_pretty[i].toUpperCase(), i)
      }
    }
  }

  setProperties(properties)
  {
    this.properties = properties
    
    if("display_type" in this.properties)
    {
      this.display_type = this.properties["display_type"]
    }

    if("label" in this.properties)
    {
      this.label_pretty = this.properties["label"]
    }

    if("visible" in this.properties)
    {
      this.visible_str = this.properties["visible"]
    }

    if("indent" in this.properties)
    {
      this.indent = Math.min(Math.max(this.properties["indent"], 0), 50)
    }

    if(this.hasPropertyFlag("hidden")) this.hidden_flag = true
  }

  replaceChar(str, replace, index) {
    let first = str.substr(0, index);
    let last = str.substr(index + 1);
      
    let new_str = first + replace + last;
    return new_str;
  }

  pushArray()
  {
    let a = this.parent

    console.log("p_before: " + this.type)

    if(!Array.isArray(a) || this.type == "undefined") return

    if(a.length > 0)
    {
      a.push(a[a.length - 1])
    }
    else
    {
      if(this.type == "string") a.push("")
      if(this.type == "number") a.push(0)
      if(this.type == "boolean") a.push(true)
    }

    console.log("p_after: " + this.parent.length)
    
  }

  popArray()
  {
    let a = this.parent

    if(!Array.isArray(a)) return
    if(a.length == 0) return

    a.pop()
  }

  initArray(type)
  {
    let a = this.parent

    if(!Array.isArray(a)) return
    if(a.length > 0) return

    this.type = type

    this.pushArray()
  }

  getMaxArrayEntryDigits()
  {
    if(!Array.isArray(this.parent)) return 1
    if(this.type == "boolean") return 1

    let max_digits = 1

    //console.log("l: " + this.parent.length)

    for(let i = 0; i < this.parent.length; i++)
    {
      let l = this.parent[i].toString().length

      if(l > max_digits)
      {
        max_digits = l
      }
    }

    return max_digits
  }

  getParentType()
  {
    if(Array.isArray(this.parent))
    {
      return "array"
    }

    return "object"
  }

  update(value)
  {
    if(typeof(value) == this.type)
    {
      this.parent[this.member] = value
    }
  }

  updateArray(index, value)
  {
    if(!Array.isArray(this.parent))
    {
      console.log("updateArray: No array.")
      return
    }

    if(typeof(value) != this.type)
    {
      console.log("updateArray: type mismatch, should: <" + 
        typeof(value) + "> is: <" + this.type + ">")
      return
    }

    if(index >= this.parent.length)
    {
      console.log("updateArray: index out of bounds.")
      return
    }

    this.parent[index] = value
  }

  computeVisibility(config_entry_dict)
  {
    if(this.visible_str == "") return

    let parts = this.visible_str.split("=")
    let entry = config_entry_dict[parts[0]]

    if(entry.getType() == "string")
    {
      this.visible = entry.getValue() == parts[1]
    }
    else if(entry.getType() == "boolean")
    {
      this.visible = (entry.getValue() ? "True" : "False") == parts[1]
    }
    else
    {
      console.log("computeVisibility: Type mismatch.")
    }
  }
}