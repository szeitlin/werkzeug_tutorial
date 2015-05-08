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
        """
        aka, 'the constructor'.

        :param config:
        :return:
        """
        self.redis = redis.Redis(config['redis_host'], config['redis_port'])
        template_path= os.path.join(os.path.dirname(__file__), 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_path), autoescape=True)

        self.url_map = Map([
            Rule('/', endpoint='new_url'),
            Rule('/<short_id>', endpoint='follow_short_link'),
            Rule('/<short_id>+', endpoint='short_link_details')
        ])
    #first view
    def on_new_url(self, request):
        error=None
        url=''
        if request.method=='POST':
            url = request.form['url']
            if not is_valid_url(url):
                error = 'Please enter a real url!'
            else:
                short_id = self.insert_url(url)
                return redirect('/%s+' % short_id)
        return self.render_template('new_url.html', error=error, url=url)

    def insert_url(self, url):
        """
        Checks to see if short_id already exists, return if yes, otherwise generate new.

        :param url:
        :return:
        """
        short_id = self.redis.get('reverse-url:' + url)
        if short_id is not None:
            return short_id
        url_num = self.redis.incr('last-url-id')
        short_id = base36_encode(url_num)
        self.redis.set('url-target:' + short_id, url)
        self.redis.set('reverse-url:' + url, short_id)
        return short_id

    def on_follow_short_link(self, request, short_id):
        """
        redirect view. looks for the link in redis and redirects to it,
        otherwise raises a NotFound exception, which will be converted by
        the dispatch_request function to a default 404 response.

        also increments a counter to track how often a link was clicked.

        note that redis only works with strings. 

        :param request:
        :param short_id:
        :return:
        """
        link_target = self.redis.get('url-target:' + short_id)
        if link_target is None:
            raise NotFound()
        self.redis.incr('click-count:' + short_id)
        return redirect(link_target)

    def on_short_link_details(self, request, short_id):
        link_target=self.redis.get('url-target:' + short_id)
        if link_target is None:
            raise NotFound()
        click_count = int(self.redis.get('click_count:' + short_id) or 0)
        return self.render_template('short_link_details.html',
                                    link_target=link_target, short_id=short_id, click_count=click_count)

    def render_template(self, template_name, **context):
        t = self.jinja_env.get_template(template_name)
        return Response(t.render(context), mimetype='text/html')

    def dispatch_request(self, request):
        """
        Sends the request and gets the response.
        Could return another wsgi app from here.

        Binds the URL map to the current environment and gets back a URLAdapter object, which is used
        to match the request or reverse URLs.

        :param request:
        :return:
        """
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            return getattr(self, 'on_' + endpoint)(request, **values)

        #if no match, will raise a NotFound
        except HTTPException as e:
            return e

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



def is_valid_url(url):
    """
    helper for on_new_url.

    :param url:
    :return: bool
    """
    parts = urlparse.urlparse(url)
    return parts.scheme in ('http', 'https')

def base36_encode(number):
    """
    helper function for creating the short id.

    :param number:
    :return:
    """
    assert number >=0, 'positive integer required'
    if number==0:
        return '0'
    base36=[]
    while number !=0:
        number, i = divmod(number,36)
        base36.append('0123456789abcdefghijklmnopqrstuvwxyz'[i])
    return ''.join(reversed(base36))

if __name__=='__main__':
    from werkzeug.serving import run_simple
    app=create_app()
    run_simple('127.0.0.1', 5000, app, use_debugger=True, use_reloader=True)
