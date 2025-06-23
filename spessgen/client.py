import typing

import spessgen.methods as methods
import spessgen.write_methods as write_methods

class ClientWriter(write_methods.WriteMethods):
    def __init__(self, converter: methods.Converter, module: str) -> None:
        super().__init__(converter)
        self.module = module

    def go(self) -> None:
        self.generated_header()

        docs = [
            self.spec.info.title + ' ' + self.spec.info.version,
            self.spec.info.description,
        ]
        self.doc_string('\n\n'.join(docs))

        self.print('from __future__ import annotations')
        self.print()
        self.print('import dataclasses')
        self.print('import typing')
        self.print()
        self.print('import spess._backend as backend')
        self.print('from spess._json import Json, from_json, to_json, Enum, datetime, date')
        if self.resolver.models_module != self.module:
            models = self.resolver.models_module
            self.print(f'import spess.{models} as {models}')
        if self.converter.responses_module != self.module:
            responses = self.converter.responses_module
            self.print(f'import spess.{responses} as {responses}')

        re_exports = ['Error', 'ClientError', 'ServerError', 'Paged']

        self.print()
        self.dunder_all(['Client'] + re_exports)

        self.print()
        for export in re_exports:
            self.print(f'{export} = backend.{export}')

        self.print()
        with self.print('class Client(backend.Backend):'):
            self.print(f'SERVER_URL = {self.spec.servers[0].url!r}')

            for method, banner in self.converter.iter_methods():
                self.write_method(method, banner)
