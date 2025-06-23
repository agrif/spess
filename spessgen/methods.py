import dataclasses
import typing

import humps

from spessgen.config import *
import spessgen.spec as spec
import spessgen.types as types

@dataclasses.dataclass
class Method:
    @dataclasses.dataclass
    class Argument:
        json_name: str
        py_name: str
        py_type: str
        optional: bool
        doc: str | None

    spec_name: str
    py_name: str
    doc: str | None
    tags: list[str]
    method: spec.Path.Method
    path: str

    path_args: list[Argument]
    query_args: list[Argument]
    body_args: list[Argument] | Argument

    py_result: str
    adhoc: bool
    paginated: bool

    @property
    def all_args(self) -> list[Argument]:
        if isinstance(self.body_args, list):
            return self.path_args + self.query_args + self.body_args
        return self.path_args + self.query_args + [self.body_args]

class Converter:
    def __init__(self, spec: spec.Spec, resolver: types.Resolver, responses_module: str | None = None) -> None:
        self.spec = spec
        self.resolver = resolver
        self.responses_module: str = responses_module if responses_module else resolver.models_module
        self.methods: dict[str, Method] = {}

        for path, info in spec.paths.items():
            self.add_path(path, info)

    def add_path(self, path: str, info: spec.Path) -> None:
        for method, op in info.methods.items():
            self.add_op(path, method, op)

    def _collect_args(self, spec_name: str, op: spec.Operation) -> tuple[list[Method.Argument], list[Method.Argument], bool]:
        path_args = []
        query_args = []
        query_args_optional = []
        paginated = False
        parameters = op.parameters if op.parameters else []
        for param in parameters:
            json_name = param.name
            if param.in_ == param.In.QUERY and json_name in {'page', 'limit'}:
                paginated = True
                continue

            try:
                stem = param.in_.value.lower() + '.'
                py_name = METHOD_ARG_NAME.get(spec_name, {})[stem + json_name]
            except KeyError:
                py_name = humps.decamelize(json_name)
                if py_name in KEYWORDS:
                    py_name += '_'

            py_type = self.resolver.resolve(spec_name + '.' + json_name, param.schema, parent=self.responses_module)

            arg = Method.Argument(
                json_name = json_name,
                py_name = py_name,
                py_type = py_type,
                optional = not param.required,
                doc = param.description,
            )

            match param.in_:
                case param.In.PATH:
                    if arg.optional:
                        raise RuntimeError(f'optional path arg: {arg!r}')
                    path_args.append(arg)
                case param.In.QUERY:
                    if arg.optional:
                        query_args_optional.append(arg)
                    else:
                        query_args.append(arg)
                case _:
                    typing.assert_never(param.in_)

        return (path_args, query_args + query_args_optional, paginated)

    def _json_schema(self, where: str, content: dict[str, spec.Operation.Content] | None) -> spec.SchemaLike:
        if content is None:
            content = {}
        try:
            return content['application/json'].schema
        except KeyError:
            raise NotImplementedError(f'no json schema found for {where}')

    def _resolve_body(self, spec_name: str, py_name: str, body: spec.Operation.RequestBody) -> list[Method.Argument] | Method.Argument:
        schema = self._json_schema(f'{spec_name} body', body.content)
        if isinstance(schema, spec.SchemaRef):
            # premade type, use it wholesale
            py_type = self.resolver.resolve(spec_name + '.body', schema, parent=self.responses_module, name_hint=py_name + 'Body')
            try:
                py_name = METHOD_ARG_NAME.get(spec_name, {})['body']
            except KeyError:
                py_name = humps.decamelize(py_type.rsplit('.')[-1])
                if py_name in KEYWORDS:
                    py_name += '_'
            return Method.Argument(
                json_name = 'body', # dummy
                py_name = py_name,
                py_type = py_type,
                doc = None,
                optional = not body.required,
            )
        else:
            # composite type, break it out into arguments
            _, ty = self.resolver.resolve_type(spec_name + '.body', schema, parent=self.responses_module, name_hint=py_name + 'Body', define=False, promote_orphans=True)
            if ty is None or not isinstance(ty.definition, types.Struct):
                raise NotImplementedError(f'non-object type in body of {spec_name}')

            args = []
            for field in ty.definition.fields.values():
                try:
                    py_name = METHOD_ARG_NAME.get(spec_name, {})['body.' + field.json_name]
                except KeyError:
                    py_name = field.py_name
                args.append(Method.Argument(
                    json_name = field.json_name,
                    py_name = py_name,
                    py_type = field.py_type,
                    doc = field.doc,
                    optional = field.optional or not body.required,
                ))
            return args

    def _resolve_response(self, spec_name: str, py_name: str, op: spec.Operation) -> tuple[str, bool]:
        if '204' in op.responses:
            # accursed 204 FIXME
            del op.responses['204']

        doc = None

        if len(op.responses) != 1:
            raise NotImplementedError(f'multiple response codes for {spec_name}')
        first, = op.responses.values()
        if first.description and not doc:
            doc = first.description
        schema = self._json_schema(f'{spec_name} response', first.content)

        adhoc = True
        props = set()
        if isinstance(schema, spec.Schema):
            if schema.properties:
                props = set(schema.properties.keys())
                if schema.type == spec.Schema.Type.OBJECT:
                    if props.issubset({'data', 'meta'}):
                        adhoc = False
                        schema = schema.properties['data']

        if isinstance(schema, spec.Schema):
            if doc and not schema.description:
                schema.description = doc

        py_result = self.resolver.resolve(spec_name + '.response', schema, parent=self.responses_module, name_hint=py_name)
        return (py_result, adhoc)

    def add_op(self, path: str, method: spec.Path.Method, op: spec.Operation) -> None:
        spec_name = op.operationId
        if spec_name in METHOD_SKIP:
            return

        try:
            py_name = METHOD_NAME[spec_name]
        except KeyError:
            py_name = spec_name
            if py_name.startswith('get-'):
                py_name = py_name.split('-', 1)[1]
            py_name = humps.dekebabize(py_name)
            if py_name in KEYWORDS:
                py_name += '_'

        doc = op.description
        if not doc:
            doc = op.summary

        # Arguments
        path_args, query_args, paginated = self._collect_args(spec_name, op)
        # Body
        body_args: list[Method.Argument] | Method.Argument = []
        if op.requestBody is not None:
            body_args = self._resolve_body(spec_name, py_name, op.requestBody)
        # Response
        py_result, adhoc = self._resolve_response(spec_name, py_name, op)

        # unwrap list[..] on paginated results
        if paginated:
            if not py_result.startswith('list[') or not py_result.endswith(']'):
                raise RuntimeError(f'paginated result for {spec_name} is not a list')
            py_result = py_result[len('list['):-len(']')]

        # construct the method and add it
        m = Method(
            spec_name = spec_name,
            py_name = py_name,
            doc = doc,
            tags = op.tags,
            path = path,
            method = method,

            path_args = path_args,
            query_args = query_args,
            body_args = body_args,

            py_result = py_result,
            adhoc = adhoc,
            paginated = paginated,
        )

        if m.py_name in self.methods:
            raise RuntimeError(f'conflicting method names: {m.py_name}')

        self.methods[m.py_name] = m

    def iter_methods(self, predicate: typing.Callable[[Method], bool] | None = None) -> typing.Iterator[tuple[Method, str | None]]:
        methods_keyed = []
        spec_tags = [tag.name for tag in self.spec.tags]
        for method in self.methods.values():
            if predicate is not None and not predicate(method):
                continue
            key = []
            for tag in method.tags:
                if tag in spec_tags:
                    key.append(spec_tags.index(tag))
                else:
                    key.append(len(spec_tags))
            key.sort()
            methods_keyed.append((key, method))

        methods_keyed.sort(key=lambda t: t[0])
        last_banner = None
        for key, method in methods_keyed:
            banner = None
            if key and key[0] < len(spec_tags):
                banner = spec_tags[key[0]]
            if banner != last_banner:
                yield method, banner
                last_banner = banner
            else:
                yield method, None
