import logging
import multiprocessing
import pathlib
import shutil

import click
import uvicorn


@click.group()
def cli():
    """Management script for orgahome."""


def default_workers() -> int:
    return (multiprocessing.cpu_count() * 2) + 1


@cli.command("uvicorn")
@click.option("-h", "--host", default="::")
@click.option("-p", "--port", default=5000, type=int)
@click.option("-w", "--workers", default=None, type=int)
@click.option("--forwarded-allow-ips", default=[], type=str, multiple=True)
@click.option("-d", "--debug", is_flag=True, default=False)
def uvicorn_command(host, port, workers, forwarded_allow_ips, debug):
    """Launch Starlette serving using uvicorn."""

    # Ensure that the emoji map is loadable.
    from orgahome.services import get_system_emoji_map

    get_system_emoji_map()

    if debug:
        asgi_app = "orgahome.app:debug_app"
        workers = None
        logging.basicConfig(level=logging.DEBUG)
    else:
        asgi_app = "orgahome.app:app"
        workers = default_workers() if workers is None else workers
        logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        host=host,
        port=port,
        app=asgi_app,
        reload=debug,
        workers=workers,
        forwarded_allow_ips=list(forwarded_allow_ips),
    )


@cli.command("compilestatic")
@click.option("-d", "--dest", type=pathlib.Path)
def compilestatic_command(dest: pathlib.Path | None = None):
    """Compile static files."""
    from orgahome.staticfiles import STATIC_COMPILED_PATH, compile_static_files

    dest = pathlib.Path(dest or STATIC_COMPILED_PATH)

    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir()

    compile_static_files(dest_path=dest)


if __name__ == "__main__":
    cli()
