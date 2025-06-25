# version dance
def _get_version():
    import importlib.metadata
    try:
        return importlib.metadata.version(__package__)
    except importlib.metadata.PackageNotFoundError:
        pass

    import pathlib
    try:
        import setuptools_scm # type: ignore
        return setuptools_scm.get_version(
            pathlib.Path(__file__).parent.parent,
            version_scheme='release-branch-semver', # must match pyproject.toml
        )
    except (ImportError, LookupError):
        pass

    return '<unknown>'

__version__ = _get_version()

# import order is somewhat fragile here
import spess.client
import spess.models
import spess.responses

# useful aliases
m = spess.models
r = spess.responses
