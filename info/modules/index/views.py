from flask import current_app, jsonify
from flask import request
from flask import session
from info import constants

from info.models import User, News
from info.modules.index import index_blu
from flask import render_template

from info.utils.response_code import RET


@index_blu.route('/')
def index():
    # 如果用户已经登陆，将当前登陆用户的数据传到模板中，供模板显示
    # 获取到当前登陆用户的id
    user_id = session.get("user_id", None)
    # 通过id获取用户信息
    user = None
    if user_id:
        try:
            user = User.query.get(user_id)
        except Exception as e:
            current_app.logger.error(e)
    new_list = []
    try:
        new_list = News.query.order_by(News.clicks.desc()).limit(6)
    except Exception as e:
        current_app.logger.error(e)
    new_dict_li = list()
    for news in new_list:
        new_dict_li.append(news.to_basic_dict())
    data = {
        "user": user.to_dict() if user else None,
        "new_dict_li": new_dict_li,
    }
    return render_template("news/index.html", data=data)


@index_blu.route("/newslist")
def get_news_list():
    """
    获取参数
    校验参数
    查询数据
    返回数据
    """
    # 获取参数
    args_dict = request.args
    print(args_dict)
    page = args_dict.get("page", "1")
    per_page = args_dict.get("per_page", constants.HOME_PAGE_MAX_NEWS)
    category_id = args_dict.get("cid", "1")

    # 校验参数
    try:
        category_id = int(category_id)
        page = int(page)
        per_page = int(per_page)
    except Exception as res:
        current_app.logger.error(res)
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 查询数据并分页
    filterr = []
    # 如果分类id不为１，　那么添加分类id的过滤
    if category_id != 0:
        filterr.append(News.category_id == category_id+1)
        print(type(category_id))

    try:
        paginates = News.query.filter(*filterr).order_by(News.create_time.desc())
        print(paginates.first())
        paginates = paginates.paginate(page, per_page, False)
        # 获取查询出来的数据
        #
        items = paginates.items
    # 获取总页数
        total_page = paginates.pages
        current_page = paginates.page
    except Exception as res:
        current_app.logger.error(res)
        return jsonify(errno=RET.DBERR, errmsg="数据查询失败")
    news_li = []
    print("before news loop")
    print(items)
    for news in items:
        news_li.append(news.to_basic_dict())
    # 返回数据
    print(total_page, current_page)
    return jsonify(errno=RET.OK, errmsg="OK",
                   totalPage=total_page,
                   currentPage=current_page,
                   newsList=news_li,
                   cid=category_id)






@index_blu.route('/favicon.ico')
def favicon():
    return current_app.send_static_file("news/favicon.ico")
