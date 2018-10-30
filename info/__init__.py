from logging.handlers import RotatingFileHandler

from flask import Flask
from flask import g
from flask import render_template
from flask import session
from flask.ext.session import Session
from flask.ext.wtf import CSRFProtect
from flask.ext.wtf.csrf import generate_csrf
from flask_sqlalchemy import SQLAlchemy

import sys
from config import *

db = SQLAlchemy()
redis_store = None  # type:StringRedis


def setup_log(config_name):
    logging.basicConfig(level=config[config_name].LOG_LEVEL)
    file_log_hander = RotatingFileHandler("logs/log", maxBytes=1024*1024*10, backupCount=10)
    formatter = logging.Formatter("%(levelname)s %(filename)s:%(lineno)d %(message)s")
    file_log_hander.setFormatter(formatter)


# 在flask扩展里面，很多都可以先初始化扩展的对象，然后调用init方法初始化
def create_app(config_name):
    # setup_log(config_name)
    app = Flask(__name__,)
    app.config.from_object(config[config_name])
    db.init_app(app)
    global redis_store
    redis_store = StrictRedis(host=config[config_name].REDIS_HOST,
                              port=config[config_name].REDIS_PORT, decode_responses=True)
    CSRFProtect(app)
    # 帮我们做了，　从cookie中取出随机值，从表单中取出随机值，然后进行校验
    # 但是没做表单和cookie中设置值 在响应中设置afert_response
    # 所以我们需要在cookie中csrf_token, 在表单中加入隐藏标签
    Session(app)
    from info.utils.common import do_index_class
    app.add_template_filter(do_index_class, "index_class")

    @app.after_request
    def after_request(response):
        csrf_token = generate_csrf()
        response.set_cookie("csrf_token", csrf_token)
        return response
    # from info.utils.common import do_index_class
    # 注册蓝图
    from info.modules.index import index_blu
    app.register_blueprint(index_blu)
    from info.modules.passport import passport_blu
    app.register_blueprint(passport_blu)
    from info.modules.news import detail_blu
    app.register_blueprint(detail_blu)
    from info.modules.profile import profile_blu
    app.register_blueprint(profile_blu)
    from info.modules.admin import admin_blu
    app.register_blueprint(admin_blu)

    from info.utils.common import user_login_data
    @app.errorhandler(404)
    @user_login_data
    def page_not_found(_):
        user = g.user
        data = {"user_info": user.to_dict() if user else None}
        return render_template('news/404.html', data=data)
    return app

