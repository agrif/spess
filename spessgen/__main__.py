import json
import pathlib
import sys

import mypy.api
from rich import print

import spessgen.client as client
import spessgen.methods as methods
import spessgen.models as models
import spessgen.spec
import spessgen.types as types
import spessgen.writer as writer

def main() -> None:
    here = pathlib.Path(__file__).parent
    spess = here / '..' / 'spess'
    with open(here / 'spacetraders.json') as f:
        spec = spessgen.spec.Spec.from_json(json.load(f))

    resolver = types.Resolver(spec, models_module='models')
    converter = methods.Converter(spec, resolver, responses_module='responses')

    checkfiles = []
    def generate(path: pathlib.Path, writer: writer.Writer) -> None:
        with open(path, 'w') as f:
            writer.generate(f)
        checkfiles.append(str(path))

    generate(spess / 'models.py', models.ModelWriter(converter, 'models'))
    generate(spess / 'responses.py', models.ModelWriter(converter, 'responses'))
    generate(spess / 'client.py', client.ClientWriter(converter, 'client'))

    #print(resolver.types)
    #print(converter.methods)

    stdout, stderr, status = mypy.api.run(['--no-incremental'] + checkfiles)
    if stdout:
        print(stdout)
    if stderr:
        print(stderr, file=sys.stderr)
    sys.exit(status)

if __name__ == '__main__':
    main()
