from flask import Flask
from app.config import Config
import os

def create_app(config_class=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    
    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass
        
    # Register blueprints
    from app.routes.main import main
    app.register_blueprint(main)
    
    return app 