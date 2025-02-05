class ContainerEntry
{
  constructor(id, name, image, short_id, status)
  {
    this.id = id
    this.name = name
    this.image = image
    //this.labels = labels
    this.short_id = short_id
    this.status = status

    this.display_name = this.name.replace("databeam-", "")
    this.display_image = this.image.split(":")[0]
    this.display_tag = this.image.split(":")[1]
  }

  getID() { return this.id }
  getName() { return this.name }
  getDisplayName() { return this.display_name }
  getImage() { return this.image }
  getDisplayImage() { return this.display_image }
  //getLabels() { return this.labels }
  getShortID() { return this.short_id }
  getStatus() { return this.status }
  getDisplayTag(){ return this.display_tag}
}