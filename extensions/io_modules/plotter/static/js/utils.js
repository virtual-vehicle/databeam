
class Utils
{
  static createNumberInput(default_value, change_callback)
  {
    let input = document.createElement("INPUT");
    input.setAttribute("type", "number");
    input.setAttribute("name", "name");
    input.value = default_value
    input.addEventListener("change", change_callback, true);
    return input
  }

  static createTextInput(default_value, change_callback)
  {
    let input = document.createElement("INPUT");
    input.setAttribute("type", "text");
    input.setAttribute("name", "name");
    input.value = default_value
    input.addEventListener("change", change_callback, true);
    return input
  }

  static createCheckBox(attributes, checked, click_callback)
  {
    let checkbox = document.createElement("INPUT");
    checkbox.setAttribute("type", "checkbox");
    checkbox.setAttribute("name", "name");
    for(let i = 0; i < attributes.length; i++) checkbox.setAttribute(attributes[i][0], attributes[i][1])
    checkbox.checked = checked
    checkbox.addEventListener("click", click_callback, true);
    return checkbox
  }

  static clamp(x, min_value, max_value)
  {
    return Math.min(Math.max(x, min_value), max_value)
  }

  static getMedian(arr)
  {
    arr.sort((a, b) => a - b);
    const middle_index = Math.floor(arr.length / 2);

    if (arr.length % 2 === 0)
    {
      return (arr[middle_index - 1] + arr[middle_index]) / 2;
    }
    else
    {
      return arr[middle_index];
    }
  }
}