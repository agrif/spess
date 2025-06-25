# stub to re-export generated code
import spess._generated.client
from spess._generated.client import *

from spess._backend import Error, ParseError, ClientError, ServerError
from spess._paged import Paged

__doc__ = spess._generated.client.__doc__

__all__ = [
    'Client', 'Error', 'ParseError', 'ClientError', 'ServerError', 'Paged',
]
