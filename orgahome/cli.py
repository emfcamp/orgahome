import multiprocessing

import click
import gunicorn.app.base
import gunicorn.config
from flask import Flask
from flask.cli import FlaskGroup
from werkzeug.middleware.proxy_fix import ProxyFix

from orgahome.app import app


def create_app():
    return app


class Gunicorn(gunicorn.app.base.BaseApplication):
    def __init__(self, *, behind_nginx=False, options=None):
        self.options = options or {}
        self.behind_nginx = behind_nginx
        super().__init__()

    def load_config(self):
        assert isinstance(self.cfg, gunicorn.config.Config)
        config = {key: value for key, value in self.options.items() if key in self.cfg.settings and value is not None}
        for key, value in config.items():
            self.cfg.set(key.lower(), value)

    def load(self):
        app = create_app()
        if self.behind_nginx:
            app.wsgi_app = ProxyFix(
                app.wsgi_app,
                x_for=1,
                x_proto=1,
                x_host=1,
                x_prefix=1,
            )
        return app


@click.group(cls=FlaskGroup, create_app=create_app)
def cli():
    """Management script for orgahome."""


def default_workers() -> int:
    return (multiprocessing.cpu_count() * 2) + 1


@cli.command("gunicorn")
@click.option("-h", "--host", default="[::]")
@click.option("-p", "--port", default=5000, type=int)
@click.option("-w", "--workers", default=None, type=int)
@click.option("--behind-nginx/--no-behind-nginx", default=False, type=bool)
def gunicorn_command(host, port, workers, behind_nginx):
    """Launch Flask serving using gunicorn."""
    options = {
        "bind": f"{host}:{port}",
        "workers": default_workers() if workers is None else workers,
        "accesslog": "-",
        "disable_redirect_access_to_syslog": True,
        "proc_name": "orgahome",
    }
    g = Gunicorn(behind_nginx=behind_nginx, options=options)
    g.run()
