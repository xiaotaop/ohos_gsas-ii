"""Resolve packaged Python extensions from the installed HAP native directory.

The map is generated before the runtime manifest and verified with the rest of
the immutable HAP payload. No URI, user file or writable-library fallback is
accepted here. Pure Python packages still use their usual runtimeRoot paths.
"""
from __future__ import annotations

import importlib.abc
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import re
import sys


class PackagedExtensionFinder(importlib.abc.MetaPathFinder):
    def __init__(self, directory: Path, modules: dict[str, str], namespaces=()):
        self.directory = directory
        self.modules = modules
        self.namespaces = frozenset(namespaces)

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.namespaces:
            # HAP archives do not retain empty directories. Preserve only the
            # namespace packages recorded before their extensions were moved.
            if importlib.machinery.PathFinder.find_spec(fullname, path) is None:
                return importlib.machinery.ModuleSpec(fullname, loader=None, is_package=True)
            return None
        filename = self.modules.get(fullname)
        if filename is None:
            return None
        source = self.directory / filename
        loader = importlib.machinery.ExtensionFileLoader(fullname, str(source))
        return importlib.util.spec_from_file_location(fullname, source, loader=loader)


def validate_map(document) -> dict[str, str]:
    if not isinstance(document, dict) or type(document.get('schemaVersion')) is not int or document.get('schemaVersion') != 1:
        raise ImportError('Invalid packaged extension map version')
    modules = document.get('modules')
    if not isinstance(modules, dict):
        raise ImportError('Invalid packaged extension map entries')
    filenames = set()
    for name, filename in modules.items():
        if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', name):
            raise ImportError('Invalid packaged extension module name')
        if not isinstance(filename, str) or not re.fullmatch(r'[A-Za-z0-9_.-]+\.so', filename):
            raise ImportError('Invalid packaged extension library name')
        if filename.casefold() in filenames:
            raise ImportError('Colliding packaged extension library names')
        filenames.add(filename.casefold())
    return dict(modules)


def validate_namespaces(document, modules):
    names = document.get('namespacePackages', [])
    if (not isinstance(names, list) or any(not isinstance(name, str) for name in names)
            or len(set(names)) != len(names)):
        raise ImportError('Invalid packaged namespace list')
    for name in names:
        if name in modules or not any(module.startswith(name + '.') for module in modules):
            raise ImportError('Namespace has no mapped descendants')
        if not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*', name):
            raise ImportError('Invalid packaged namespace name')
    return frozenset(names)


def install(runtime_root: str, native_directory: str) -> int:
    index = Path(runtime_root) / 'bridge' / 'native-module-map.json'
    if not index.is_file():
        return 0  # Host tests and older, unmapped runtimes keep normal imports.
    document = json.loads(index.read_text(encoding='utf-8'))
    modules = validate_map(document)
    namespaces = validate_namespaces(document, modules)
    directory = Path(native_directory)
    if not directory.is_absolute() or not directory.is_dir():
        raise ImportError('Installed native library directory is unavailable')
    for filename in modules.values():
        library = directory / filename
        if not library.is_file() or library.is_symlink():
            raise ImportError('A packaged native extension is missing')
    for finder in sys.meta_path:
        if isinstance(finder, PackagedExtensionFinder):
            if finder.directory == directory and finder.modules == modules and finder.namespaces == namespaces:
                return len(modules)
            raise ImportError('A different packaged extension map is already active')
    # Prefer the declared, installed native copy over any matching .so in a
    # writable package directory. Unmapped modules continue to PathFinder.
    sys.meta_path.insert(0, PackagedExtensionFinder(directory, modules, namespaces))
    return len(modules)
