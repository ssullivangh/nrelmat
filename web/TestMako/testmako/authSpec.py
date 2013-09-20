
import ldap

# Returns True if userid,pswd are authenticated; else False.

def authCheckUseridPassword( userid, pswd):

  # OPT_X_TLS_REQUIRE_CERT
  # Use the following if we don't have a
  # valid certificate for the domain.
  ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)

  # Disable chasing of referrals by LDAP.
  ldap.set_option(ldap.OPT_REFERRALS, 0)

  conn = ldap.initialize( 'ldaps://ds.nrel.gov:636/')   # server

  # Bind.
  # Throws exception ldap.INVALID_CREDENTIALS.
  res = False
  try:
    # Can use 'NREL_NT\\' + userid  or:  userid + '@nrel.gov'
    bind = conn.simple_bind_s( 'NREL_NT\\' + userid, pswd)
    res = True
  except ldap.INVALID_CREDENTIALS:
    res = False
  #print ('    ***** authSpec.AuthCheckUseridPassword: userid: %s  res A: %s') \
  #  % (userid, res,)

  authNames = [
    'btumas',
    'hpeng',
    'pgraf',
    'pzawadzk',
    'slany',
    'ssulliva',
    'vstevano',
  ]
  if res and userid not in authNames: res = False
  #print ('    ***** authSpec.AuthCheckUseridPassword: userid: %s  res B: %s') \
  #  % (userid, res,)
  return res


# Returns a list of groups for userid.

def authGetUserGroups( userid, request):
  grps = ['grpAlpha']
  return grps

