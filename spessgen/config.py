# Many of these overrides refer to an item by spec_name. These are derived
# from the name of the item in the OpenAPI spec file, but it gets a bit
# hard to follow. In the generated source, each item is preceded by a
# spec_name: <name> comment to help.
#
# Field and argument names use the unmodified JSON names. Types are derived
# from the schema name, and nested schemas use the containing field name.
# Methods use the operationId and argument JSON names, as well as 'body'
# and 'response' namespaces.
#
# Types
#
#          root schema: Foo
#           field type: Foo.bar
#        nested fields: Foo.someField.bar
#
# Methods
#
#        method itself: get-foo
#        argument type: get-foo.fieldName
#    body type (whole): get-foo.body
#   body type (fields): get-foo.body.fieldName
#        response type: get-foo.response

# python keywords to avoid in python names
KEYWORDS: set[str] = {
    'yield',
}

# type names, from spec_name to local python type name (no parent)
TYPE_NAME: dict[str, str] = {
    # info/symbol swap, give symbol a shorter name
    'FactionTrait': 'FactionTraitInfo',
    'FactionTraitSymbol': 'FactionTrait',
    # remove name conflict with renamed ShipNavStatus
    'get-status.response': 'ServerStatus',
    # these need a shorter name, they're used too often
    'ShipNavFlightMode': 'FlightMode',
    'ShipNavStatus': 'ShipStatus',
    # more info/symbol swap
    'WaypointModifier': 'WaypointModifierInfo',
    'WaypointModifierSymbol': 'WaypointModifier',
    'WaypointTrait': 'WaypointTraitInfo',
    'WaypointTraitSymbol': 'WaypointTrait',
}

# field type overrides, from spec_name, field_json_name to full python type
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
    'get-error-codes.response.errorCodes': {
        'code': 'int',
    },
    # missing faction symbol
    'get-my-factions.response': {
        'symbol': 'models.FactionSymbol',
    },
    # this is a date, not a str
    'get-status.response': {
        'resetDate': 'date',
    },
    # this is a datetime, not str
    'get-status.response.health': {
        'lastMarketUpdate': 'datetime',
    },
    # this is a datetime, not str
    'get-status.response.serverResets': {
        'next': 'datetime',
    },
    # agents don't use faction symbol type
    'PublicAgent': {
        'startingFaction': 'models.FactionSymbol',
    },
    # more missing trade symbol
    'ShipModificationTransaction': {
        'tradeSymbol': 'models.TradeSymbol',
    },
    # more missing faction symbol
    'ShipRegistration': {
        'factionSymbol': 'models.FactionSymbol',
    },
}

# name of methods to skip, by spec_name (aka operationId)
METHOD_SKIP: set[str] = {
    # needs support for additionalProperties on objects
    'get-supply-chain',
    # needs websockets
    'websocket-departure-events',
}

# method names, from spec_name to python name
METHOD_NAME: dict[str, str] = {
    # don't auto-remove get- on these, it conflicts with another method
    'get-repair-ship': 'get_repair_ship',
    'get-scrap-ship': 'get_scrap_ship',
}

# method argument names, from spec_name, <type>.jsonArgName to python name
# type is one of path, query, body
# a lone 'body' refers to a whole-body argument
METHOD_ARG_NAME: dict[str, dict[str, str]] = {
    # transfer-cargo has ambiguous shipSymbols
    'transfer-cargo': {
        'body.shipSymbol': 'to_ship',
        'path.shipSymbol': 'from_ship',
    },
}
