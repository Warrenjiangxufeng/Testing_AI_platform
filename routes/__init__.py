from .dashboard import dashboard_bp
from .testcases import testcases_bp
from .ai_test import ai_bp
from .api_test import api_bp
from .perf_test import perf_bp
from .bugs import bugs_bp


def register_blueprints(app):
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(testcases_bp, url_prefix="/testcases")
    app.register_blueprint(ai_bp, url_prefix="/ai-test")
    app.register_blueprint(api_bp, url_prefix="/api-test")
    app.register_blueprint(perf_bp, url_prefix="/perf-test")
    app.register_blueprint(bugs_bp, url_prefix="/bugs")

