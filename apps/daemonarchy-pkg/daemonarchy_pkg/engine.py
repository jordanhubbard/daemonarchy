"""Load the installer's engine modules, which have no .py suffix or a hyphen in the name.

The same files the installer runs: `parallel-fetch` (plan parsing, exact catalogue bytes, the
`@@plan` and `@@fetch` contract) and `progress-model` (the counters and estimates). The package
installs copies next to the application; on the live image and in a checkout they are found where
the installer keeps them. DAEMONARCHY_PKG_ENGINE names a directory to look in first.
"""
import importlib.machinery
import importlib.util
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent


def search_path():
    candidates = []
    if os.environ.get('DAEMONARCHY_PKG_ENGINE'):
        candidates.append(Path(os.environ['DAEMONARCHY_PKG_ENGINE']))
    candidates += [
        HERE.parent / 'engine',
        Path('/usr/local/libexec/daemonarchy-pkg'),
        Path('/usr/local/libexec/daemonarchy-installer'),
        HERE.parents[2] / 'overlay/usr/local/libexec/daemonarchy-installer',   # a checkout
    ]
    return candidates


_loaded = {}


def load(name):
    """The module for an engine file such as 'parallel-fetch' or 'progress-model'."""
    if name in _loaded:
        return _loaded[name]
    for directory in search_path():
        for filename in (name, name + '.py'):
            path = directory / filename
            if path.is_file():
                loader = importlib.machinery.SourceFileLoader(name.replace('-', '_'), str(path))
                spec = importlib.util.spec_from_loader(loader.name, loader)
                module = importlib.util.module_from_spec(spec)
                loader.exec_module(module)
                _loaded[name] = module
                return module
    raise ImportError(f'engine module {name} not found in: ' + ', '.join(str(c) for c in search_path()))
