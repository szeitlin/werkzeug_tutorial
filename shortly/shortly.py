__author__ = 'szeitlin'

#following http://werkzeug.pocoo.org/docs/0.10/tutorial/

import os
import redis
import urlparse
from werkzeug.wrappers import Request, Response
from werkzeug.routing import Map, Rule
from werkzeug.exceptions import HTTPException, NotFound
from werkzeug.wsgi import SharedDataMiddleware
from werkzeug.utils import redirect
from jinja2 import Environment, FileSystemLoader

class Shortly(object):

    def __init__(self, config):
        self.redis = redis.Redis(config['redis_host'], config['redis_port'])

    def dispatch_request(self, request):
        """
        Sends the request and gets the response.
        Could return another wsgi app from here.

        :param request:
        :return:
        """
        return Response('hello world!')

    def wsgi_app(self, environ, start_response):
        """
        Creates the request object, calls the dispatch_request method to get the response.

        :param environ:
        :param start_response:
        :return:
        """
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        """
        Dispatches to wsgi_app.

        :param environ:
        :param start_response:
        :return:
        """
        return self.wsgi_app(environ, start_response)


def create_app(redis_host=('localhost'), redis_port=6379, with_static=True):
    """
    Creates an instance of our app, passes configuration and can add middleware.

    :param redis_host:
    :param redis_port:
    :param with_static:
    :return:
    """
    app = Shortly({
        'redis_host': redis_host,
        'redis_port': redis_port
    })
    if with_static:
        app.wsgi_app=SharedDataMiddleware(app.wsgi_app, {
            '/static': os.path.join(os.path.dirname(__file__), 'static')
        })
    return app

if __name__=='__main__':
    from werkzeug.serving import run_simple
    app=create_app()
    run_simple('127.0.0.1', 5000, app, use_debugger=True, use_reloader=True)
