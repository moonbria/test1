from flask import g
from flask import render_template

from info.utils.common import user_login_data
from . import detail_blu



@detail_blu.route("/<int:news_id>")
@user_login_data
def detail_index(news_id):
    user = g.user
    data = {
        "user": user.to_dict() if user else None,
    }
    return render_template("news/detail.html", data=data)
