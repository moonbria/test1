from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager

from info import db
from info import create_app
# 通过指定的配置名字创建对应的app
from info.models import User


app = create_app("development")
manager = Manager(app)
Migrate(app, db)
manager.add_command('db', MigrateCommand)


@manager.option("-n", "-name", dest="name")
@manager.option("-p", "-password", dest="password")
def createsuperuser(name, password):
    """创建管理员用户"""
    if not all([name, password]):
        print("参数不足")
        return
    user = User()
    user.mobile = name
    user.nick_name = name
    user.password = password
    user.is_admin = True

    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        print(e)
        db.session.rollback()


if __name__ == '__main__':
    manager.run()
