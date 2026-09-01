from flask import Flask
from flask import jsonify

from config import Config
from extensions import db


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__)
    app.config.from_object(config_class)
    # 确保本地运行总是读取最新模板，避免旧缓存导致 UI 错乱
    app.config.setdefault("TEMPLATES_AUTO_RELOAD", True)
    app.config.setdefault("SEND_FILE_MAX_AGE_DEFAULT", 0)

    db.init_app(app)

    from routes import register_blueprints

    register_blueprints(app)

    with app.app_context():
        db.create_all()
        from seed import seed_if_empty

        seed_if_empty()

    @app.route("/api/version")
    def api_version():
        return jsonify({"version": app.config.get("APP_VERSION", "1.0.0")})

    return app


app = create_app()
