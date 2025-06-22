# python keywords to avoid in python names
KEYWORDS: set[str] = {
    'yield',
}

# type names, from spec_name to python type name
TYPE_NAME: dict[str, str] = {
    # info/symbol swap, give symbol a shorter name
    'FactionTrait': 'FactionTraitInfo',
    'FactionTraitSymbol': 'FactionTrait',
    # these need a shorter name, they're used too often
    'ShipNavFlightMode': 'FlightMode',
    'ShipNavStatus': 'ShipStatus',
    # remove name conflict with renamed ShipNavStatus
    'status': 'ServerStatus',
    # more info/symbol swap
    'WaypointModifier': 'WaypointModifierInfo',
    'WaypointModifierSymbol': 'WaypointModifier',
    'WaypointTrait': 'WaypointTraitInfo',
    'WaypointTraitSymbol': 'WaypointTrait',
}

# field type overrides, from spec_name, json_name to python type
STRUCT_FIELD_TYPE: dict[str, dict[str, str]] = {
    # agents don't use faction symbol type
    'Agent': {
        'startingFaction': 'models.FactionSymbol',
    },
    # actually most things don't use the faction symbol type
    'Contract': {
        'factionSymbol': 'models.FactionSymbol',
    },
    # missing trade symbol
    'ContractDeliverGood': {
        'tradeSymbol': 'models.TradeSymbol',
    },
    # these are almost certainly ints, not floats
    'errorCode': {
        'code': 'int',
    },
    # this is a datetime, not str
    'health': {
        'lastMarketUpdate': 'datetime',
    },
    # missing faction symbol
    'my_faction': {
        'symbol': 'models.FactionSymbol',
    },
    # agents don't use faction symbol type
    'PublicAgent': {
        'startingFaction': 'models.FactionSymbol',
    },
    # this is a datetime, not str
    'serverResets': {
        'next': 'datetime',
    },
    # more missing trade symbol
    'ShipModificationTransaction': {
        'tradeSymbol': 'models.TradeSymbol',
    },
    # more missing faction symbol
    'ShipRegistration': {
        'factionSymbol': 'models.FactionSymbol',
    },
    # this is a date, not a str
    #'status': {
    #    'resetDate': 'date',
    #},
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
