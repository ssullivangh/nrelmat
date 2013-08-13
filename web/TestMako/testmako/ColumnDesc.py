
class ColumnDesc:
  def __init__( self, dbName, tag, fmt, desc):
    self.dbName = dbName
    self.tag = tag
    self.fmt = fmt
    self.desc = desc

  def __str__( self):
    res = 'dbName: %s  tag: %s' % (self.dbName, self.tag,)
    return res

