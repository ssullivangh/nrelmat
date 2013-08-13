

# Returns True if userid,pswd are authenticated; else False.

def authCheckUseridPassword( userid, pswd):
  pswdMap = {
    # Note: must also add to groupMap, below.
    'peter'   : 'peter',
    'steve'   : 'steve',
    'vladan'  : 'vladan',
  }
  res = False
  if pswdMap.has_key( userid) and pswdMap[userid] == pswd: res = True
  print ('    ***** authSpec.AuthCheckUseridPassword: userid: %s  res: %s') \
    % (userid, res,)
  return res


# Returns a list of groups for userid.

def authGetUserGroups( userid, request):
  groupMap = {
    'peter'   : ['grpAlpha'],
    'steve'   : ['grpAlpha'],
    'vladan'  : ['grpAlpha'],
  }
  grps = groupMap.get( userid, [])
  print '    ***** authSpec.authGetuserGroups: userid: %s  grps: %s' \
    % (userid, grps,)
  return grps

