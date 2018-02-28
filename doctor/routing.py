import functools
import inspect
from typing import Callable, List, Tuple

from flask_restful import Resource

from doctor.flask import handle_http
from doctor.utils import get_params_from_func


class HTTPMethod(object):
    """Represents and HTTP method and it's configuration.

    When instantiated the logic attribute will have 3 attributes added to it:
        - `_doctor_allowed_exceptions` - A list of excpetions that are allowed
          to be re-reaised if encountered during a request.
        - `_doctor_params` - A :class:`~doctor.utils.Params` instance.
        - `_doctor_signature` - The parsed function Signature.
        - `_doctor_title` - The title that should be used in api documentation.

    :param method: The HTTP method.  One of: (delete, get, post, put).
    :param logic: The logic function to be called for the http method.
    :param allowed_exceptions: If specified, these exception classes will be
        re-raised instead of turning them into 500 errors.
    :param title: An optional title for the http method.  This will be used
        when generating api documentation.
    """
    def __init__(self, method: str, logic: Callable,
                 allowed_exceptions: List=None, title: str=None):
        self.method = method

        # Add doctor attributes to logic.  We do a check to ensure some
        # attributes aren't already set in the event that
        # doctor.utils.add_param_annotations was used to add additional
        # request parameters to the logic function that aren't part of it's
        # signature.
        if not hasattr(logic, '_doctor_signature'):
            logic._doctor_signature = inspect.signature(logic)
        if not hasattr(logic, '_doctor_params'):
            logic._doctor_params = get_params_from_func(logic)
        logic._doctor_allowed_exceptions = allowed_exceptions
        logic._doctor_title = title
        self.logic = logic


def delete(func: Callable, allowed_exceptions: List=None,
           title: str=None) -> HTTPMethod:
    """Returns a HTTPMethod instance to create a DELETE route.

    :see: :class:`~doctor.routing.HTTPMethod`
    """
    return HTTPMethod('delete', func, allowed_exceptions=allowed_exceptions,
                      title=title)


def get(func: Callable, allowed_exceptions: List=None,
        title: str=None) -> HTTPMethod:
    """Returns a HTTPMethod instance to create a GET route.

    :see: :class:`~doctor.routing.HTTPMethod`
    """
    return HTTPMethod('get', func, allowed_exceptions=allowed_exceptions,
                      title=title)


def post(func: Callable, allowed_exceptions: List=None,
         title: str=None) -> HTTPMethod:
    """Returns a HTTPMethod instance to create a POST route.

    :see: :class:`~doctor.routing.HTTPMethod`
    """
    return HTTPMethod('post', func, allowed_exceptions=allowed_exceptions,
                      title=title)


def put(func: Callable, allowed_exceptions: List=None,
        title: str=None) -> HTTPMethod:
    """Returns a HTTPMethod instance to create a PUT route.

    :see: :class:`~doctor.routing.HTTPMethod`
    """
    return HTTPMethod('put', func, allowed_exceptions=allowed_exceptions,
                      title=title)


def create_http_method(logic: Callable, http_method: str) -> Callable:
    """Create a handler method to be used in a handler class.

    :param callable logic: The underlying function to execute with the
        parsed and validated parameters.
    :param str http_method: HTTP method this will handle.
    :returns: A handler function.
    """
    @functools.wraps(logic)
    def fn(handler, *args, **kwargs):
        return handle_http(handler, args, kwargs, logic)
    return fn


class Route(object):

    """Represents a route.

    :param route: The route path, e.g. `r'^/foo/<int:foo_id>/?$'`
    :param methods: A tuple of defined HTTPMethods for the route.
    :param heading: An optional heading that this route should be grouped
        under in the api documentation.
    :param base_handler_class: The base handler class to use.
    :param handler_name: The name that should be given to the handler class.
    """
    def __init__(self, route: str, methods: Tuple[HTTPMethod],
                 heading: str=None, base_handler_class=Resource,
                 handler_name: str=None):
        self.base_handler_class = base_handler_class
        self.handler_name = handler_name
        self.heading = heading
        self.methods = methods
        self.route = route


def create_routes(routes: Tuple[HTTPMethod]) -> List[Tuple[str, Resource]]:
    """Creates handler routes from the provided routes.

    :param routes: A tuple containing the route and another tuple with
        all http methods allowed for the route.
    :returns: A list of tuples containing the route and generated handler.
    """
    created_routes = []
    for r in routes:
        handler = None
        for method in r.methods:
            logic = method.logic
            http_method = method.method
            http_func = create_http_method(logic, http_method)
            handler_name = r.handler_name or logic.__name__
            handler_methods_and_properties = {
                '__name__': handler_name,
                '_doctor_heading': r.heading,
                http_method: http_func,
            }
            if handler is None:
                handler = type(
                    handler_name, (r.base_handler_class,),
                    handler_methods_and_properties)
            else:
                setattr(handler, http_method, http_func)
                # This is specific to Flask.  Its MethodView class
                # initializes the methods attribute in __new__ so we
                # need to add all the other http methods we are defining
                # on the handler after it gets created by type.
                if hasattr(handler, 'methods'):
                    handler.methods.append(http_method.upper())
        created_routes.append((r.route, handler))
    return created_routes