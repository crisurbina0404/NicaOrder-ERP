from flask import Flask
from .config import Config
from .extensions import db
from .db_init import init_db
from .auth import load_user
from .menu import get_menu_items


def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(Config)

    import os
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    db.init_app(app)

    @app.before_request
    def before_request():
        load_user()

    @app.context_processor
    def inject_menu():
        return dict(menu_items=get_menu_items())

    from .routes.main import main_bp
    from .routes.auth import auth_bp
    from .routes.products import products_bp
    from .routes.suppliers import suppliers_bp
    from .routes.purchases import purchases_bp
    from .routes.inventory import inventory_bp
    from .routes.customers import customers_bp
    from .routes.sales import sales_bp
    from .routes.hr import hr_bp
    from .routes.payroll import payroll_bp
    from .routes.reports import reports_bp
    from .routes.admin import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(suppliers_bp)
    app.register_blueprint(purchases_bp)
    app.register_blueprint(inventory_bp)
    app.register_blueprint(customers_bp)
    app.register_blueprint(sales_bp)
    app.register_blueprint(hr_bp)
    app.register_blueprint(payroll_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(admin_bp)

    with app.app_context():
        init_db()

    return app
