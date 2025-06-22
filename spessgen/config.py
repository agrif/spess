# python keywords to avoid in python names
KEYWORDS: set[str] = {
    'yield',
}

# name of methods to skip, by operationId
METHOD_SKIP: set[str] = {
    # needs websockets
    'websocket-departure-events',
    # needs support for additionalProperties on objects
    'get-supply-chain',
}

# method names, from operationId to python name
METHOD_NAME: dict[str, str] = {
    # don't auto-remove get- on these, it conflicts with another method
    'get-repair-ship': 'get_repair_ship',
    'get-scrap-ship': 'get_scrap_ship',
}

# method argument names, from operationId, type.jsonName to python name
# type is one of path, query, body
# a lone 'body' refers to a whole-body argument
METHOD_ARG_NAME: dict[str, dict[str, str]] = {
    # transfer-cargo has ambiguous shipSymbols
    'transfer-cargo': {
        'path.shipSymbol': 'from_ship',
        'body.shipSymbol': 'to_ship',
    },
}
