class MetaEntry
{
  constructor(meta_key, meta_value)
  {
    this.meta_key = meta_key
    this.meta_value = meta_value
  }

  getKey() { return this.meta_key; }
  getValue() { return this.meta_value; }
}