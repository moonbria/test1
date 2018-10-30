from flask import request
import random
import re
from flask import current_app, jsonify
from flask import g
from flask import make_response
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
import time
from info import constants, db
from info import redis_store
from info.lib.yuntongxun.sms import CCP
from info.utils.captcha.captcha import captcha
from info.utils.image_storage import storage
from info.utils.response_code import RET
from info.modules.passport import passport_blu
from info.models import User, Category, News
from info.modules.profile import profile_blu
from info.utils.common import user_login_data
from datetime import datetime, timedelta

from . import admin_blu


@admin_blu.route("/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "GET":
        # 去session　中取到指定的值
        user_id = session.get("user_id", None)
        is_admin = session.get("is_admin", False)
        if user_id and is_admin:
            return redirect(url_for("admin_index"))
        return render_template("admin/login.html")

    # 取到登陆的参数
    username = request.form.get("username")
    password = request.form.get("password")
    if not all([username, password]):
        return render_template("admin/login.html", errmsg="参数错误")

    try:
        user = User.query.filter(User.mobile == username).first()
    except Exception as e:
        current_app.logger.error(e)
        return render_template("admin/login.html", errmsg="数据错误")

    if not user:
        return render_template("admin/login.html", errmsg="用户名错误")

    if not user.check_password(password):
        return render_template("admin/login.html", errmsg="密码错误")

    if not user.is_admin:
        return render_template("admin/login.html", errmsg="用户不是管理员")

    session["user_id"] = user.id
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile
    session["is_admin"] = True

    #  跳转到后台管理主页，暂未实现
    return redirect(url_for("admin.admin_index"))


@admin_blu.route("/index")
@user_login_data
def admin_index():
    user = g.user
    return render_template("admin/index.html", user=user.to_dict())


@admin_blu.before_request
def before_request():
    # 判断如果不是登陆页面的请求
    if not request.url.endswith(url_for("admin.admin_login")):
        user_id = session.get("user_id")
        is_admin = session.get("is_admin", False)

        if not user_id or not is_admin:
            # 判断当前是否有用户登陆，或者是否是管理员，如果不是，直接重定向到项目首页
            return redirect("/")


@admin_blu.route("/user_count")
def user_count():
    # 查询总人数
    total_count = 0
    try:
        total_count = User.query.filter(User.is_admin == False).count()
    except Exception as e:
        current_app.logger.error(e)

    # 查询月新增数
    mon_count = 0
    try:
        now = time.localtime()
        mon_begin = "%d-%02d-01" % (now.tm_year, now.tm_mon)
        mon_begin_date = datetime.strptime(mon_begin, "%Y-%m-%d")
        mon_count = User.query.filter(User.is_admin==False,
                                      User.create_time > mon_begin_date).count()
    except Exception as e:
        current_app.logger.error(e)

    day_count = 0
    try:
        day_begin = "%d-%02d-%02d" % (now.tm_year, now.tm_mon, now.tm_mday)
        day_begin_date = datetime.strptime(day_begin, "%Y-%m-%d")
        day_count = User.query.filter(User.is_admin==False,
                                      User.create_time >= day_begin_date).count()
    except Exception as e:
        current_app.logger.error(e)

    # 查询图表信息
    # 获取到当天00:00:00时间
    now_date = datetime.strptime(datetime.now().strftime("%Y-%m-%d"), "%Y-%m-%d")
    print(now_date)
    # 定义空数组，保存数据
    active_date = list()
    active_count = list()

    # 依次添加数据，再反转
    for i in range(0, 31):
        begin_date = now_date - timedelta(days=i)
        end_date = now_date - timedelta(days=(i - 1))
        active_date.append(begin_date.strftime("%Y-%m-%d"))
        count = 0
        try:
            count = User.query.filter(User.is_admin == False,
                                     User.last_login >= begin_date,
                                     User.last_login < end_date).count()
            print(count)
        except Exception as e:
            current_app.logger.error(e)
        active_count.append(count)

    active_date.reverse()
    active_count.reverse()

    data = {"total_count": total_count, "mon_count": mon_count, "day_count": day_count,
            "active_date": active_date, "active_count": active_count}

    return render_template("admin/user_count.html", data=data)


@admin_blu.route("/user_list")
def user_list():
    """获取用户列表"""
    # 获取参数
    page = request.args.get("p", 1)
    try:
        print(page)
        page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        page = 1

    # 设置变量默认值
    users = []
    current_page = 1
    total_page = 1

    #查询数据
    try:
        paginate = User.query.filter(User.is_admin == False)\
            .order_by(User.last_login.desc())\
            .paginate(page, constants.ADMIN_NEWS_PAGE_MAX_COUNT, False)
        users = paginate.items
        current_page = paginate.page
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    # 将模型列表转换成字典列表
    users_list = []
    for user in users:
        users_list.append(user.to_admin_dict())

    context = {
        "total_page": total_page,
        "current_page": current_page,
        "users": users_list
    }
    return render_template("admin/user_list.html", data=context)


@admin_blu.route("/news_review")
def news_review():
    """返回待审核新闻列表"""
    page = request.args.get("p", 1)
    keywords = request.args.get("keywords", "")
    try:
        page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        page = 1

    news_list = list()
    current_page = 1
    total_page = 1

    try:
        filters = [News.status != 0]
        # 如果有关键词
        if keywords:
            # 添加关键字检索选项
            filters.append(News.title.contains(keywords))
        paginate = News.query.filter(*filters)\
            .order_by(News.create_time.desc())\
            .paginate(page, constants.ADMIN_NEWS_PAGE_MAX_COUNT, False)
        news_list = paginate.items
        current_page = paginate.page
        total_page = paginate.pages
    except Exception as e:
        current_app.error(e)

    news_dict_list = list()
    for news in news_list:
        news_dict_list.append(news.to_review_dict())

    data = {
        "total_page": total_page,
        "current_page": current_page,
        "news_list": news_dict_list
    }
    return render_template("admin/news_review.html", data=data)


@admin_blu.route("/news_review_detail", methods=["GET", "POST"])
def news_review_detail():
    """新闻审核"""
    # 获取新闻id
    if request.method == "GET":
        news_id = request.args.get("news_id")
        if not news_id:
            data = {
                "errmsg": "未查询到数据"
            }
            return render_template("admin/news_review_detail.html", data=data)
        # 通过id查询新闻
        news = None
        try:
            news = News.query.get(news_id)
        except Exception as e:
            current_app.logger.error(e)

        if not news:
            data = {
                "errmsg": "未查询到数据"
            }
            return render_template("admin/news_review_detail.html", data=data)

        # 返回数据
        data = {
            "news": news.to_dict()
        }
        return render_template("admin/news_review_detail.html", data=data)

    # 执行审核操作
    # 1. 获取参数
    news_id = request.json.get("news_id")
    action = request.json.get("action")

    #2. 判断参数
    if not all([news_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    if action not in ("accept", "reject"):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    news = None
    try:
        #　3. 查询新闻
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)

    if not news:
        return jsonify(errno=RET.NODATA, errmsg="未查询到数据")

    if action == "accept":
        news.status = 0
    else:
        # 拒绝通过，需要获取原因
        reason = request.json.get("reason")
        if not reason:
            return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
        news.reason = reason
        news.status = -1
    # 保存数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")
    return jsonify(errno=RET.OK, errmsg="操作成功")


@admin_blu.route("/news_edit", methods=["GET", "POST"])
def news_edit():
    """返回新闻列表"""

    page = request.args.get("p", "1")
    print(page)
    a = re.match(r"^\d*", page)
    b = re.findall(r"""keywords=(\w*)""", page)
    print(b)
    page = a.group()
    if b != []:
        b = b[0]
        keywords = b
    else:
        keywords = None
        b = ""
    try:
        page = int(page)
    except Exception as e:
        current_app.logger.error(e)
        page = 1

    news_list = list()
    current_page = 1
    total_page = 1
    try:
        filters = list()
        # 如果有关键词
        if keywords:
            # 添加关键词的检索选项
            filters.append(News.title.contains(keywords))
        # 查询
        paginate = News.query.filter(*filters)\
            .order_by(News.create_time.desc())\
            .paginate(page, constants.ADMIN_NEWS_PAGE_MAX_COUNT, False)
        news_list = paginate.items
        current_page = paginate.page
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    news_dict_list = list()
    for news in news_list:
        news_dict_list.append(news.to_basic_dict())

    data = {
        "total_page": total_page,
        "current_page": current_page,
        "new_list": news_dict_list,
        "last_input": b
    }
    if request.method == "GET":
        return render_template("admin/news_edit.html", data=data)
    # return jsonify(errno=RET.OK, errmsg="OK")
    return render_template("admin/news_edit.html", data=data)


@admin_blu.route("/news_edit_detail", methods=["GET", "POST"])
def news_edit_detail():
    """新闻编辑详情"""
    if request.method == "GET":
        # 获取参数
        news_id = request.args.get("news_id")
        if not news_id:
            data = {
                "errmsg": "没有找到新闻"
            }
            return render_template("admin/news_edit_detail.html", data=data)
        # 查询新闻
        news = None
        try:
            news = News.query.get(news_id)
        except Exception as e:
            current_app.logger.error(e)

        if not news:
            data = {
                "errmsg": "没有找到新闻"
            }
            return render_template("admin/news_edit_detail.html", data=data)

        categories = Category.query.all()
        categories_li = []
        for category in categories:
            c_dict = category.to_dict()
            c_dict["is_selected"] = False
            if category.id == News.category_id:
                c_dict["is_selected"] = True
            categories_li.append(c_dict)

        # 移除最新分类
        categories_li.pop(0)
        data = {
            "news": news.to_dict(),
            "categories": categories_li
        }
        return render_template("admin/news_edit_detail.html", data=data)

    news_id = request.form.get("news_id")
    title = request.form.get("title")
    digest= request.form.get("digest")
    content = request.form.get("content")
    index_image = request.form.get("index-image")
    categery_id = request.form.get("category_id")
    # 1.1　判断数据是否有值：
    if not all([title, digest, content, categery_id]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数有误")
    print(title, digest, content, categery_id)
    news = None
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
    if not news:
        return jsonify(errno=RET.NODATA, errmsg="未找到新闻数据")

    # 1.2 尝试读取图片
    if index_image:
        try:
            index_image = index_image.read()
        except Exception as e:
            return jsonify(errno=RET.PARAMERR, errmsg="参数有误")

        # 2. 将标题图片上传到七牛
        try:
            key = storage(index_image)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.THIRDERR, errmsg="上传图片错误")
        news.index_image_url = constants.QINIU_DOMIN_PREFIX + key

    # 3. 设置相关数据
    news.title = title
    news.digest = digest
    news.content = content
    news.category_id = categery_id

    # 4. 保存到数据库
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")
    # 5. 返回结果

    return jsonify(errno=RET.OK, errmsg="编辑成功")


@admin_blu.route("/news_category")
def get_news_category():
    # 获取所有的分类数据
    categories = Category.query.all()
    # 定义列表保存分类数据
    categories_dicts = []

    for category in categories:
        # 获取字典
        cate_dict = category.to_dict()
        # 拼接内容
        categories_dicts.append(cate_dict)

    categories_dicts.pop(0)
    # 返回内容
    data = {
        "categories": categories_dicts
    }
    return render_template("admin/news_type.html", data=data)


@admin_blu.route("/add_category", methods=["POST"])
def add_category():
    """修改或者添加分类"""
    category_id = request.json.get("id")
    category_name = request.json.get("name")
    print(category_name)
    if not category_name:
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    # 判断是否有分类id
    if category_id:
        try:
            category = Category.query.get(category_id)
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="查询数据失败")

        if not category:
            return jsonify(errno=RET.NODATA, errmsg="未查询到分类信息")

        category.name = category_name
        return jsonify(errno=RET.OK, errmsg="保存数据成功")

    else:
        # 如果没有分类id, 添加分类
        try:
            new_category = Category()
            new_category.id = category_id
            new_category.name = category_name
            db.session.add(new_category)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(e)
            db.session.rollback()
            return jsonify(errno=RET.DBERR, errmsg="保存数据失败")
        return jsonify(errno=RET.OK, errmsg="保存数据成功")

