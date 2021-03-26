import logging
import falcon
import simplejson as json

from msapp import config
apiconfig = config.c['api']

class AuthMiddleware(object):
    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def process_request(self, req, resp):
        token = req.get_header('X-Auth-Token')
        challenges = ['Token']
        if token is None:
            description = ('Please provide an auth token '
                           'as part of the request.')
            raise falcon.HTTPUnauthorized('Auth token required',
                                          description,
                                          challenges)
        if not self._token_is_valid(token):
            description = ('The provided auth token is not valid. '
                           'Please request a new token and try again.')
            raise falcon.HTTPUnauthorized('Authentication required',
                                          description,
                                          challenges)

    def _token_is_valid(self, token):
        if token is None:
            return False
        # Reject empty API key or unconfigured API key
        result = True if apiconfig['apikey'] and apiconfig['apikey'] != "" else False
        if result is False:
            self.logger.error("REST API key must not be empty.")
        # Match API key
        result = True if result is True and token == apiconfig['apikey'] else False
        if result is False:
            self.logger.error("REST API key does not match, service rejected.")
        return result

class RequireJSON(object):
    def process_request(self, req, resp):
        if not req.client_accepts_json:
            raise falcon.HTTPNotAcceptable(
                'This API only supports responses encoded as JSON.')
        if req.method in ('POST', 'PUT'):
            if not req.content_type or 'application/json' not in req.content_type:
                raise falcon.HTTPUnsupportedMediaType(
                    'This API only supports requests encoded as JSON.')

class JSONTranslator(object):
    def process_request(self, req, resp):
        # req.stream corresponds to the WSGI wsgi.input environ variable,
        # and allows you to read bytes from the request body.
        #
        # See also: PEP 3333
        if req.content_length in (None, 0):
            if req.method in ('POST', 'PUT'):
                raise falcon.HTTPBadRequest('Empty request body',
                                            'A valid JSON document is required.')
            else:
                # Nothing to do, empty body is allowed for GET, DELETE, etc.
                # If query string is used (i.e. parameters after ?), decode them and pass dict to context.
                if req.query_string:
                    req.context['query'] = falcon.util.uri.parse_query_string(req.query_string, keep_blank_qs_values=True)
                return
        body = req.stream.read()
        if not body:
            raise falcon.HTTPBadRequest('Empty request body',
                                        'A valid JSON document is required.')
        try:
            req.context['doc'] = json.loads(body.decode('utf-8'), use_decimal=True)
        except (ValueError, UnicodeDecodeError):
            raise falcon.HTTPError(falcon.HTTP_753,
                                   'Malformed JSON',
                                   'Could not decode the request body. The '
                                   'JSON was incorrect or not encoded as '
                                   'UTF-8.')

    def process_response(self, req, resp, resource, req_succeeded):
        if 'result' not in req.context:
            return
        resp.body = json.dumps(req.context['result'])

def max_body(limit):
    def hook(req, resp, resource, params):
        length = req.content_length
        if length is not None and length > limit:
            msg = ('The size of the request is too large. The body must not '
                   'exceed ' + str(limit) + ' bytes in length.')
            raise falcon.HTTPRequestEntityTooLarge('Request body is too large', msg)
    return hook

app = falcon.API(middleware=[
    AuthMiddleware(),
    RequireJSON(),
    JSONTranslator(),
])
