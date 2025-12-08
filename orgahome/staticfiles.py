"""Simple handling of digested static files."""

import abc
import base64
import hashlib
import json
import os
import pathlib
import re
import typing
from collections.abc import Collection, Iterable

import jinja2
import jinja2.runtime
from starlette import staticfiles
from starlette.requests import Request
from starlette.templating import Jinja2Templates

STATIC_SOURCE_PATH = pathlib.Path(__file__).parent / "static"
STATIC_COMPILED_PATH = pathlib.Path(__file__).parent / "dist"
MANIFEST_FILENAME = ".staticmanifest.json"

FILENAME_HASH_FUNC = hashlib.sha256
FILENAME_HASH_LEN = FILENAME_HASH_FUNC().digest_size * 2


class StaticFilesBase(abc.ABC):
    def __init__(self, static_route: str = "static"):
        self.static_route = static_route

    def register_template_functions(self, templates: Jinja2Templates) -> None:
        @jinja2.pass_context
        def static_url_for(context: jinja2.runtime.Context, path: str) -> str:
            request: Request = context["request"]
            return request.url_for(self.static_route, path=self.hash_path(path))

        templates.env.globals["static_url_for"] = static_url_for
        templates.env.globals["static_sri_hash"] = lambda path: self.get_sri_hash(path)

    @abc.abstractmethod
    def hash_path(self, file: str) -> str | None:
        pass

    @abc.abstractmethod
    def hashed_path_to_file(self, path: str) -> tuple[str, os.stat_result | None] | None:
        pass

    @abc.abstractmethod
    def get_sri_hash(self, file: str) -> str | None:
        pass


def hashed_filename(root: pathlib.Path, file: pathlib.PurePath) -> pathlib.PurePath:
    filehash = FILENAME_HASH_FUNC((root / file).read_bytes()).hexdigest()
    return file.with_stem(f"{file.stem}.{filehash}")


HASHED_STEM_REGEX = re.compile(r"^(.*)[.][a-z0-9]{" + str(FILENAME_HASH_LEN) + "}$")


def sri_hash(root: pathlib.Path, file: pathlib.PurePath) -> str:
    filehash = hashlib.sha256((root / file).read_bytes()).digest()
    return f"sha256-{base64.b64encode(filehash).decode('utf-8')}"


def lookup_path(
    directories: Iterable[pathlib.Path], filenames: Collection[pathlib.PurePath]
) -> tuple[str, os.stat_result | None] | None:
    for directory in directories:
        for filename in filenames:
            disk_path = directory / filename
            if not disk_path.is_relative_to(directory):
                return None  # misbehaving client
            try:
                stat = disk_path.stat()
                return str(disk_path), stat
            except FileNotFoundError:
                continue
    return None


class DevelopmentStaticFiles(StaticFilesBase):
    def __init__(self, static_dir: pathlib.Path = STATIC_SOURCE_PATH, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.static_dir = static_dir

    def get_serving_directories(self) -> list[pathlib.Path]:
        return [self.static_dir]

    def resolve_path(self, file: str) -> pathlib.PurePath | None:
        resolved_path = self.static_dir.joinpath(file)
        try:
            relative_path = resolved_path.relative_to(self.static_dir)
        except ValueError:
            return None
        if not resolved_path.exists():
            return None
        return relative_path

    def hash_path(self, file: str) -> str | None:
        resolved_path = self.resolve_path(file)
        if not resolved_path:
            return None
        return str(hashed_filename(self.static_dir, resolved_path))

    def hashed_path_to_file(self, path: str) -> tuple[str, os.stat_result | None] | None:
        file = pathlib.PurePath(path)
        file_candidates: list[pathlib.PurePath] = [file]

        re_match = HASHED_STEM_REGEX.search(file.stem)
        if re_match:
            file_candidates.append(file.with_stem(re_match.group(1)))
        return lookup_path([self.static_dir], file_candidates)

    def get_sri_hash(self, file: str) -> str | None:
        resolved_path = self.resolve_path(file)
        if not resolved_path:
            return None
        return sri_hash(self.static_dir, resolved_path)


class ManifestEntry(typing.TypedDict):
    hashed_path: str
    sri_hash: str


class ManifestStaticFiles(StaticFilesBase):
    def __init__(
        self,
        static_dir: pathlib.Path = STATIC_SOURCE_PATH,
        serving_dir: pathlib.Path = STATIC_COMPILED_PATH,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.static_dir = static_dir
        self.serving_dir = serving_dir
        self.manifest = self.load_manifest()

    def get_serving_directories(self) -> list[pathlib.Path]:
        return [self.serving_dir, self.static_dir]

    def load_manifest(self) -> dict[str, ManifestEntry]:
        with open(self.serving_dir / MANIFEST_FILENAME) as f:
            return json.load(f)

    def hash_path(self, file: str) -> str | None:
        return self.manifest.get(file, {}).get("hashed_path")

    def hashed_path_to_file(self, path: str) -> tuple[str, os.stat_result | None] | None:
        return lookup_path([self.serving_dir, self.static_dir], [pathlib.PurePath(path)])

    def get_sri_hash(self, file: str) -> str | None:
        return self.manifest.get(file, {}).get("sri_hash")


def compile_static_files(
    source_path: pathlib.Path = STATIC_SOURCE_PATH, dest_path: pathlib.Path = STATIC_COMPILED_PATH
) -> None:
    manifest = {}
    for dirpath, dirnames, filenames in source_path.walk():
        for filename in filenames:
            filepath = dirpath / filename
            relative_to_source_root = pathlib.PurePath(filepath.relative_to(source_path))
            hashed_name = hashed_filename(source_path, relative_to_source_root)
            manifest[str(relative_to_source_root)] = ManifestEntry(
                hashed_path=str(hashed_name), sri_hash=sri_hash(source_path, relative_to_source_root)
            )
            target_filepath = dest_path / hashed_name
            target_filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.copy(target_filepath)
    with open(dest_path / MANIFEST_FILENAME, "w") as f:
        json.dump(manifest, f, indent=2)


class StaticFilesServer(staticfiles.StaticFiles):
    def __init__(self, static_files: StaticFilesBase):
        self.static_files = static_files
        super().__init__()

    def lookup_path(self, path: str) -> tuple[str, os.stat_result | None]:
        result = self.static_files.hashed_path_to_file(path)
        if not result:
            return "", None
        return result
