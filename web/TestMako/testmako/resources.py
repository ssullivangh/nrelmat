
import pyramid.security as security



class AuthRootFactory(object):   # xxx shouldn't this extend dict?

  __acl__ = [
    (security.Allow, security.Everyone,      'permView'),
    ###(security.Allow, 'grpAlpha',          'permEdit'),
    (security.Allow, security.Authenticated, 'permEdit'),
  ]

  def __init__(self, request):
    bugLev = 0
    if bugLev >= 5:
      print '\nresources.AuthRootFactory: init: url: %s' % (request.url,)
    if not (request.path.startswith('/_debug_toolbar/static/')
      or request.path == '/static/images/favicon.ico'):

      # See: site-packages/webob/request.py: as_bytes()
      if bugLev >= 5:
        print '  method: %s' % (request.method,)
        print '  http_version: %s' % (request.http_version,)
        print '  type(  request): %s' % (type(request),)
        print '  request.matched_route: %s' % (request.matched_route,)
        # Following dies for notFounds
        #print '  request.current_route_url(): %s' \
        #  % (request.current_route_url(),)
        print '  request.GET: %s' % (request.GET,)
        print '  request.POST: %s' % (request.POST,)
        print '  request.body: %s' % (request.body,)
        print '  request.content_length: %s' % (request.content_length,)
        print '  request.content_type: %s' % (request.content_type,)
        print '  request.date: %s' % (request.date,)
        print '  request.headers: %s' % (request.headers,)
        print '  request.host: %s' % (request.host,)
        print '  request.host_port: %s' % (request.host_port,)
        print '  request.host_url: %s' % (request.host_url,)
        print '  request.http_version: %s' % (request.http_version,)
        print '  request.method: %s' % (request.method,)
        print '  request.params: %s' % (request.params,)
        print '  request.path: %s' % (request.path,)
        print '  request.path_info: %s' % (request.path_info,)
        print '  request.pragma: %s' % (request.pragma,)
        print '  request.query_string: %s' % (request.query_string,)
        print '  request.range: %s' % (request.range,)
        print '  request.scheme: %s' % (request.scheme,)
        print '  request.script_name: %s' % (request.script_name,)
        print '  request.server_name: %s' % (request.server_name,)
        print '  request.server_port: %s' % (request.server_port,)
        print '  request.session: %s' % (request.session,)
        print '  request.text: %s' % (request.text,)
        print '  request.url: %s' % (request.url,)
        print '  request.urlargs: %s' % (request.urlargs,)
        print '  request.user_agent: %s' % (request.user_agent,)

