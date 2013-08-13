
import os
# import cPickle
import psycopg2

from pyramid.config import Configurator
from pyramid.authentication import AuthTktAuthenticationPolicy
from pyramid.authorization import ACLAuthorizationPolicy
import pyramid_beaker

from testmako.authSpec import authGetUserGroups



# xxx del:
#def getStorageLen( obj):
#  stg = cPickle.dumps( obj)
#  return len( stg)







def main(global_config, **settings):
  ''' This function returns a Pyramid WSGI application.
  '''

  # Print global_config
  # Command line parms like pserve development.int alpha=aaa
  # show up here as global_config['alpha'] == 'aaa'.

  buglev = int( settings['buglev'])
  if buglev >= 1:
    print 'init:main: cwd: %s' % (os.getcwd(),)
    print '\ninit:main: global_config type: %s' % (type(global_config),)
    keys = global_config.keys()
    keys.sort()
    for key in keys:
      print '  global_config[%s]: %s' % (key, global_config[key],)


  # Print settings
  # Items in the development.ini file like beta = bbb
  # show up here as settings['beta'] == 'bbb'.
  print '\ninit:main: settings type: %s' % (type(settings),)
  keys = settings.keys()
  keys.sort()
  for key in keys:
    msg = repr( settings[key])
    if len(msg) > 1000: msg = msg[:1000] + '...'
    print '  settings[%s]: %s' % (key, msg,)


  # Set up configuration

  # Can spec the root factory either here or per route,
  # with 'factory' parm to config.add_route.
  config = Configurator( settings=settings,
    root_factory = 'testmako.resources.AuthRootFactory')

  # Session caching
  pyramid_beaker.set_cache_regions_from_settings( settings)

  session_factory = pyramid_beaker.session_factory_from_settings(settings)
  config.set_session_factory( session_factory)

  print '\ninit.main: config: %s' %( config,)



  # Set up authentication
  # See http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/security.html#creating-your-own-authentication-policy

  class WrapAuthenticate( object):

    def __init__(self, policy):
      self.ppolicy = policy
      pass

    def authenticated_userid(self, request):
      '''Returns the authenticated userid or None
      '''
      buglev = int( request.registry.settings['buglev'])
      if buglev >= 5:
        print '\nWrapAuthenticate.authenticated_userid:'
        print '  self: %s' % (self,)
        print '  method: %s  url: %s  http_version: %s' \
          % (request.method, request.url, request.http_version,)
      res = self.ppolicy.authenticated_userid( request)
      if buglev >= 5: print '  res: %s' % (res,)
      return res

    def unauthenticated_userid(self, request):
      '''Returns the *unauthenticated* userid -- just the raw
         userid extracted from the request, without checking for auth.
      '''
      buglev = int( request.registry.settings['buglev'])
      if buglev >= 5:
        print '\nWrapAuthenticate.unauthenticated_userid:'
        print '  self: %s' % (self,)
        print '  method: %s  url: %s  http_version: %s' \
          % (request.method, request.url, request.http_version,)
      res = self.ppolicy.unauthenticated_userid( request)
      if buglev >= 5: print '  res: %s' % (res,)
      return res

    def effective_principals(self, request):
      '''Returns a sequence of the effective principals
         including the userid and all groups, including system
         groups such as pyramid.security.Everyone and
         pyramid.security.Authenticated.
      '''
      buglev = int( request.registry.settings['buglev'])
      if buglev >= 5:
        print '\nWrapAuthenticate.effective_principals:'
        print '  self: %s' % (self,)
        print '  method: %s  url: %s  http_version: %s' \
          % (request.method, request.url, request.http_version,)
      res = self.ppolicy.effective_principals( request)
      if buglev >= 5: print '  res: %s' % (res,)
      return res

    def remember(self, request, principal, **kw):
      '''Returns a set of headers suitable for remembering the
         principal when set in a response.
      '''
      buglev = int( request.registry.settings['buglev'])
      if buglev >= 5:
        print '\nWrapAuthenticate.remember:'
        print '  self: %s' % (self,)
        print '  method: %s  url: %s  http_version: %s' \
          % (request.method, request.url, request.http_version,)
        print '  principal: %s' % (principal,)
        print '  kw: %s' % (kw,)
      res = self.ppolicy.remember( request, principal, **kw)
      if buglev >= 5: print '  res: %s' % (res,)
      #
      # res is a list of header pairs [(name,value),...] like:
      #   [('Set-Cookie', 'auth_tkt="b1f6103...38YWE%3D!userid_type:b64unicode"; Path=/'),
      #    ('Set-Cookie', 'auth_tkt="b1f6103...38YWE%3D!userid_type:b64unicode"; Path=/; Domain=localhost'),
      #    ('Set-Cookie', 'auth_tkt="b1f6103...38YWE%3D!userid_type:b64unicode"; Path=/; Domain=.localhost')]
      #
      return res

    def forget(self, request):
      '''Returns a set of headers suitable for forgetting the
         principal when set in a response.
      '''
      buglev = int( request.registry.settings['buglev'])
      if buglev >= 5:
        print '\nWrapAuthenticate.forget:'
        print '  self: %s' % (self,)
        print '  method: %s  url: %s  http_version: %s' \
          % (request.method, request.url, request.http_version,)
      res = self.ppolicy.forget( request)
      if buglev >= 5: print '  res: %s' % (res,)
      #
      # res is a list of header pairs [(name,value),...] like:
      #   [('Set-Cookie', 'auth_tkt=""; Path=/; Max-Age=0; Expires=Wed, 31-Dec-97 23:59:59 GMT'),
      #    ('Set-Cookie', 'auth_tkt=""; Path=/; Domain=localhost; Max-Age=0; Expires=Wed, 31-Dec-97 23:59:59 GMT'),
      #    ('Set-Cookie', 'auth_tkt=""; Path=/; Domain=.localhost; Max-Age=0; Expires=Wed, 31-Dec-97 23:59:59 GMT')]
      #
      return res

  catePolicy = AuthTktAuthenticationPolicy(
      'k21ljxbv32jkdh32sd8u93hslki502slkj23lb',
      callback=authGetUserGroups, hashalg='sha512')
  # xxx how to check buglev?
  print '\ninit.main: catePolicy: ', catePolicy

  config.set_authentication_policy( WrapAuthenticate( catePolicy))



  # Set up authorization
  # See http://docs.pylonsproject.org/projects/pyramid/en/latest/narr/security.html#creating-your-own-authorization-policy
  # xxx all the print calls here need to check buglev, but how?

  class WrapAuthorize( object):

    def __init__(self, policy):
      self.ppolicy = policy
      pass

    def permits( self, context, principals, permission):
      '''Returns True if any of the principals is allowed the
         permission in the current context, else False.
      '''

      res = self.ppolicy.permits( context, principals, permission)
      if buglev >= 5:
        print '\nWrapAuthorize.permits:'
        print '  self: ', self
        print '  context: ', context
        print '  principals: ', principals
        print '  permission: ', permission
        print '  res: ', res
      return res

    def principals_allowed_by_permission( self, context, permission):
      '''Returns a set of principal identifiers allowed by the
         permission in context.  This method will only be called if
         using the pyramid.security.principals_allowed_by_permission API
      '''

      res = self.ppolicy.principals_allowed_by_permission(
        context, permission)
      if buglev >= 5:
        print '\nWrapAuthorize.principals_allowed_by_permission:************'
        print '  self: ', self
        print '  context: ', context
        print '  principals: ', principals
        print '  res: ', res
      return res

  rizePolicy = ACLAuthorizationPolicy()
  # xxx how to check buglev?
  print '\ninit.main: rizePolicy: ', rizePolicy
  config.set_authorization_policy( WrapAuthorize( rizePolicy))

  # Set up routes
  config.add_static_view('static', 'static', cache_max_age=3600)
  config.add_route('rtLogin',   '/login')
  config.add_route('rtLogout',  '/logout')
  config.add_route('rtHome',    '/home')
  config.add_route('rtQueryStd',  '/queryStd*queryRest')
                                               # The * matches all rest
  config.add_route('rtQueryAdv',  '/queryAdv*queryRest')
  config.add_route('rtDetail',  '/detail*queryRest')
  config.add_route('rtVisualize',  '/visualize*queryRest')
  config.add_route('rtDownload',  '/download*queryRest')
  config.add_route('rtContrib',  '/contrib*queryRest')

  config.add_notfound_view('.views:vwNotFound')

  # Or we could use in views:
  # @notfound_view_config()
  # def vwNotFound(...)

  # Or we could use:
  # def notFoundFunc(request):
  #   return Response('Not Found', status='404 Not Found')
  # config.add_notfound_view( notFoundFunc)

  # Or we could just send notFound to home,
  # but then the browser shows the incorrect url with the home page.
  # config.add_route( 'rtNotFound', '/*unused')  # The * matches all rest.
  # And in views have
  #   @view_config(route_name='rtNotFound', renderer='tmNotFound.mak')
  #   def vwNotFound(...)

  # Or we could add_route with a redirect:
  # def redirFunc(request):
  #   return HTTPFound(
  #     location='%s?message="Redirected to home from %s"' \
  #     % ( request.route_url('rtHome'), request.url))
  # config.add_route( redirFunc, '/*unused')  # The * matches all rest.
  # And in the dict returned by views.py vhome:
  #   ..., message = request.GET.get('message', None), ...

  # Also could have:
  # def forbiddenFunc(request):
  #   return Response('Not Found', status='404 Not Found')
  # config.add_forbidden_view( forbiddenFunc)


  config.scan()

  return config.make_wsgi_app()



def throwerr( msg):
  raise Exception( msg)
