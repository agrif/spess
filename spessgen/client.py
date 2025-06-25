import typing

import spessgen.methods as methods
import spessgen.write_methods as write_methods

class ClientWriter(write_methods.WriteMethods):
    def go(self) -> None:
        self.generated_header()

        docs = [
            self.spec.info.title + ' ' + self.spec.info.version,
            self.spec.info.description,
        ]
        self.doc_string('\n\n'.join(docs))

        self.print('from __future__ import annotations')
        self.print()
        self.print('import spess._backend as backend')
        self.print('from spess._json import to_json')
        if self.resolver.models_module != self.module:
            models = self.resolver.models_module
            self.print(f'import spess.{models} as {models}')
        self.print('from spess._paged import Paged')
        if self.converter.responses_module != self.module:
            responses = self.converter.responses_module
            self.print(f'import spess.{responses} as {responses}')

        self.print()
        self.dunder_all(['Client'])

        self.print()
        with self.print('class Client(backend.Backend):'):
            self.print(f'SERVER_URL = {self.spec.servers[0].url!r}')

            for method, banner in self.converter.iter_methods(self.converter.methods):
                self.write_method(method, banner)
