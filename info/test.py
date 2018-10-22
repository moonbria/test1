from . import db
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash


class BaseTable(object):
    create_time = db.Column("create_time", db.DateTime, default=datetime.now())
    update_time = db.Column("update_time", db.DateTime, default=datetime.now(), onupdate=datetime.now())


tb_follow_table = db.Table(
    "users_fans",
    db.Column("follower_id", db.Integer, db.ForeignKey("user_info.id")),
    db.Column("followed_id", db.Integer, db.ForeignKey("user_info.id")),
)

tb_collection_table = db.Table(
    "user_collection",
    db.Column("user_id", db.Integer, db.ForeignKey("user_info.id")),
    db.Column("news_id", db.Integer, db.ForeignKey()),
    db.Column("create_time", db.Integer)
)


class User(BaseTable, db.Model):
    __tablename__ = "user_info"
    id = db.Column("id", db.Integer, primary_key=True)
    nick_name = db.Column("nick_name", db.String(20))
    avatar_url = db.Column("avatar_url", db.String(60))
    mobile = db.Column("mobile", db.Integer)
    password_hash = db.Column("password_hash", db.String(64))
    last_login = db.Column("last_login", db.DateTime)
    id_admin = db.Column("is_admin", db.B)  # TODO 布尔型怎么写
    signature = db.Column("signature", db.String(30))
    gender = db.Column(db.Enum("MAN", "WOMEN"), default="MAN")


