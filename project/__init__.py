from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from os import environ, path
from dotenv import load_dotenv

# init SQLAlchemy so we can use it later in our models
db = SQLAlchemy()

basedir = path.abspath(path.dirname(__file__))
print(basedir)
load_dotenv(path.join(basedir, '.env'))

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = environ.get('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = environ.get('SQLALCHEMY_DATABASE_URI')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = environ.get('SQLALCHEMY_TRACK_MODIFICATIONS')

    db.init_app(app)

    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        # since the user_id is just the primary key of our user table, use it in the query for the user
        return User.query.get(int(user_id))

    # blueprint for auth routes in our app
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)

    # blueprint for non-auth parts of app
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # blueprint for algo parts of app
    from .algorithm import algo as algo_blueprint
    app.register_blueprint(algo_blueprint)

    app.run(host="0.0.0.0", port=80)

    return app