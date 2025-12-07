import multiprocessing
import typing

import click
import uvicorn
from a2wsgi import WSGIMiddleware
from flask import Flask
from flask.cli import FlaskGroup
from starlette.applications import Starlette
from starlette.routing import ASGIApp, Mount
from starlette.staticfiles import StaticFiles

from orgahome.app import app


def create_app():
    return app


def create_asgi_app():
    flask_app = create_app()
    flask_app.static_folder = None
    routes = [
        Mount("/static", app=StaticFiles(packages=[("orgahome", "static")])),
        Mount("/", app=typing.cast(ASGIApp, WSGIMiddleware(flask_app))),
    ]
    return Starlette(routes=routes)


@click.group(cls=FlaskGroup, create_app=create_app)
def cli():
    """Management script for orgahome."""


def default_workers() -> int:
    return (multiprocessing.cpu_count() * 2) + 1


@cli.command("uvicorn")
@click.option("-h", "--host", default="::")
@click.option("-p", "--port", default=5000, type=int)
@click.option("-w", "--workers", default=None, type=int)
@click.option("--forwarded-allow-ips", default=[], type=str, multiple=True)
def uvicorn_command(host, port, workers, forwarded_allow_ips):
    """Launch Flask serving using uvicorn."""
    config = uvicorn.Config(
        host=host,
        port=port,
        app=create_asgi_app(),
        workers=default_workers() if workers is None else workers,
        forwarded_allow_ips=list(forwarded_allow_ips),
    )
    server = uvicorn.Server(config)
    server.run()
