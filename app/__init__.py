"""Aplicación Flask: fábrica y configuración."""
import os
from pathlib import Path

from flask import Flask

from . import db as database


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(exist_ok=True)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "solo-desarrollo-cambiar"),
        SELLO_SECRET=os.environ.get("SELLO_SECRET", "solo-desarrollo-cambiar-sello"),
        BASE_URL=os.environ.get("BASE_URL", "http://localhost:5000"),
        DATABASE=os.path.join(app.instance_path, "creditos.db"),
    )
    if config:
        app.config.update(config)

    app.teardown_appcontext(database.close_db)

    # En servicios gratuitos el disco se borra al reiniciar: si no hay base, se recrea con datos simulados.
    if not app.config.get("TESTING") and not os.path.exists(app.config["DATABASE"]):
        with app.app_context():
            database.init_db()
            database.seed_db()

    from .views import bp
    app.register_blueprint(bp)

    @app.cli.command("init-db")
    def init_db_cmd():
        """Crea las tablas y carga datos simulados."""
        database.init_db()
        database.seed_db()
        print("Base de datos creada con datos simulados.")

    return app
