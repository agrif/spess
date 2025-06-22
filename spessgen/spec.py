from __future__ import annotations

import dataclasses
import enum
import types
import typing

__all__ = [
    'Spec', 'Info', 'Server', 'Tag', 'Components', 'SecurityScheme', 'Schema',
    'SchemaRef', 'SchemaEmpty', 'SchemaLike', 'Path', 'Operation',
]

class JsonError(Exception):
    def __init__(self, typ: typing.Any, val: typing.Any) -> None:
        super().__init__(f'expected {typ!r}, got {val!r}')

# mini json
def from_json(cls: type, v: typing.Any) -> typing.Any:
    original_cls = cls
    origin = typing.get_origin(cls)
    args = typing.get_args(cls)
    if origin is not None:
        cls = origin

    if cls == typing.Any:
        return v
    elif not isinstance(cls, type):
        raise JsonError(original_cls, v)
    elif issubclass(cls, JsonFormat):
        if isinstance(v, dict) and all(isinstance(k, str) for k in v):
            return cls.from_json(v)
        else:
            raise JsonError(original_cls, v)
    elif issubclass(cls, dict) and len(args) == 2 and issubclass(args[0], str):
        if isinstance(v, dict):
            return {k: from_json(args[1], val) for k, val in v.items()}
        else:
            raise JsonError(original_cls, v)
    elif issubclass(cls, list) and len(args) == 1:
        if isinstance(v, list):
            return [from_json(args[0], val) for val in v]
        else:
            raise JsonError(original_cls, v)
    elif issubclass(cls, enum.Enum):
        return cls(v)
    elif issubclass(cls, (bool, float, int, str, types.NoneType)):
        if isinstance(v, cls):
            return v
        elif issubclass(cls, float) and isinstance(v, int):
            return float(v)
        else:
            raise JsonError(original_cls, v)
    elif issubclass(cls, types.UnionType):
        excs = []
        for subcls in args:
            try:
                return from_json(subcls, v)
            except Exception as e:
                excs.append(e)
        raise ExceptionGroup(repr(original_cls), excs)
    else:
        raise JsonError(original_cls, v)

@dataclasses.dataclass
class JsonFormat:
    @classmethod
    def from_json(cls, v: dict[str, typing.Any]) -> typing.Self:
        kwargs = {}
        hints = typing.get_type_hints(cls)
        for f in dataclasses.fields(cls):
            typ = typing.get_origin(hints[f.name])
            args = typing.get_args(hints[f.name])
            if typ is None:
                typ = hints[f.name]

            if issubclass(typ, types.UnionType) and types.NoneType in args:
                val = v.get(f.name.rstrip('_'))
            else:
                val = v[f.name.rstrip('_')]
            kwargs[f.name] = from_json(hints[f.name], val)
        return cls(**kwargs)

@dataclasses.dataclass
class Spec(JsonFormat):
    openapi: str
    info: Info
    components: Components
    paths: dict[str, Path]
    # security: ?
    servers: list[Server]
    tags: list[Tag]

@dataclasses.dataclass
class Info(JsonFormat):
    @dataclasses.dataclass
    class Contact(JsonFormat):
        email: str
        name: str

    @dataclasses.dataclass
    class License(JsonFormat):
        name: str
        url: str

    title: str
    version: str
    description: str
    contact: Contact
    license: License

@dataclasses.dataclass
class Server(JsonFormat):
    description: str
    url: str

@dataclasses.dataclass
class Tag(JsonFormat):
    description: str
    name: str

@dataclasses.dataclass
class Components(JsonFormat):
    callbacks: dict[str, typing.Any]
    links: dict[str, typing.Any]
    securitySchemes: dict[str, SecurityScheme]
    schemas: dict[str, Schema]

@dataclasses.dataclass
class SecurityScheme(JsonFormat):
    type: str
    scheme: str
    description: str
    bearerFormat: str

@dataclasses.dataclass
class Schema(JsonFormat):
    class Type(enum.Enum):
        ARRAY = 'array'
        BOOLEAN = 'boolean'
        INTEGER = 'integer'
        NULL = 'null'
        NUMBER = 'number'
        OBJECT = 'object'
        STRING = 'string'

    class Format(enum.Enum):
        DATE_TIME = 'date-time'
        DOUBLE = 'double'
        INT64 = 'int64'
        INTEGER = 'integer'
        URI = 'uri'

    type: Type | None = None
    description: str | None = None
    format: Format | None = None

    # type == 'object'
    properties: dict[str, SchemaLike] | None = None
    required: list[str] | None = None

    # type == 'string'
    enum: list[str] | None = None

    # type == 'array'
    items: SchemaLike | None = None

    allOf: list[SchemaLike] | None = None
    anyOf: list[SchemaLike] | None = None
    additionalProperties: SchemaLike | None = None

@dataclasses.dataclass
class SchemaRef(JsonFormat):
    ref: str

    @classmethod
    def from_json(cls, v: dict[str, typing.Any]) -> typing.Self:
        ref = from_json(str, v['$ref'])
        return cls(ref=ref)

@dataclasses.dataclass
class SchemaEmpty(JsonFormat):
    @classmethod
    def from_json(cls, v: dict[str, typing.Any]) -> typing.Self:
        if len(v) == 0:
            return cls()
        raise JsonError({}, v)

SchemaLike: typing.TypeAlias = SchemaEmpty | SchemaRef | Schema

@dataclasses.dataclass
class Path(JsonFormat):
    class Method(enum.Enum):
        GET = 'get'
        PATCH = 'patch'
        POST = 'post'

    methods: dict[Method, Operation]

    @classmethod
    def from_json(cls, v: dict[str, typing.Any]) -> typing.Self:
        methods = {}
        for k, val in v.items():
            methods[cls.Method(k)] = from_json(Operation, val)
        return cls(methods)

@dataclasses.dataclass
class Operation(JsonFormat):
    @dataclasses.dataclass
    class Parameter(JsonFormat):
        class In(enum.Enum):
            PATH = 'path'
            QUERY = 'query'

        name: str
        in_: In
        description: str | None
        required: bool | None
        schema: SchemaLike

    @dataclasses.dataclass
    class Content(JsonFormat):
        schema: SchemaLike

    @dataclasses.dataclass
    class RequestBody(JsonFormat):
        content: dict[str, Operation.Content]
        required: bool | None

    @dataclasses.dataclass
    class Response(JsonFormat):
        description: str
        content: dict[str, Operation.Content] | None

    operationId: str
    summary: str
    tags: list[str]
    description: str
    # security: ?
    parameters: list[Parameter] | None
    requestBody: RequestBody | None
    responses: dict[str, Response]
