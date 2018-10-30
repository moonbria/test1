from flask import abort
from flask import current_app, jsonify
from flask import g
from flask import redirect
from flask import render_template
from flask import request
from info import constants, db
from info.utils.image_storage import storage
from info.utils.response_code import RET
from info.models import User, Category, News
from info.modules.profile import profile_blu
from info.utils.common import user_login_data


@profile_blu.route("/base_info", methods=["GET", "POST"])
@user_login_data
def user_center():
    user = g.user
    if request.method == "GET":
        return render_template("news/user_base_info.html",
                               data={
                                   "user": user.to_dict()
                               })
    # 如果请求的方式是post
    # 代表修改的是用户数据
    # 1. 取到传入的参数
    nick_name = request.json.get("nick_name")
    signature = request.json.get("signature")
    gender = request.json.get("gender")
    print(nick_name, signature, gender)
    # 2. 校验参数
    if not all([nick_name, signature, gender]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    if gender not in ("WOMEN", "MAN"):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    user.signature = signature
    user.nick_name = nick_name
    user.gender = gender
    return jsonify(errno=RET.OK, errmsg="OK")


@profile_blu.route('/info')
@user_login_data
def user_info():
    user = g.user
    if not user:
        # 代表没有登录，重定向到首页
        return redirect("/")
    data = {"user": user.to_dict()}
    a = user.to_dict()
    print(a["avatar_url"])
    return render_template('news/user.html', data=data)


@profile_blu.route("/pic_info", methods=["GET", "POST"])
@user_login_data
def pic_info():
    user = g.user
    if request.method == "GET":
        data = {
            "user_info": user.to_dict()
        }
        return render_template("news/user_pic_info.html", data=data)
    # 1. 获取到上传的文件
    try:
        avater_file = request.files.get("avatar").read()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="读取文件出错")

    # 2. 再将文件上传到七牛云
    try:
        url = storage(avater_file)
        print(url)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="上传图片错误")
    # 3. 设置用户模型相关数据
    try:
        user.avatar_url = url
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存用户数据错误")

    # 4. 返回上传的结果<avatar_url>
    data = {
        "avatar_url": constants.QINIU_DOMIN_PREFIX + url
    }
    return jsonify(errno=RET.OK, errmsg="OK", data=data)


@profile_blu.route("/pass_info", methods=["POST", "GET"])
@user_login_data
def pass_info():
    user = g.user
    if request.method == "GET":
        return render_template("news/user_pass_info.html")

    # 1. 获取传入的参数
    data_dict = request.json
    print(data_dict)
    old_password = data_dict.get("old_password")
    new_password = data_dict.get("new_password")
    print(old_password, new_password)

    if not all([old_password, new_password]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 2. 获取当前登陆用户的信息
    user = g.user
    if not user.check_password(old_password):
        return jsonify(errno=RET.PWDERR, errmsg="原密码错误")

    # 更新数据
    user.password = new_password
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(errno=RET.DBERR, errmsg="保存数据失败")
    return jsonify(errno=RET.OK, errmsg="保存成功")


@profile_blu.route("/collection")
@user_login_data
def user_collection():
    # 获取页数
    p = request.args.get("p", 1)
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1
    user = g.user
    collections = []
    current_page = 1
    total_page = 1
    try:
        # 进行分页数据查询
        paginate = user.collection_news.paginate(p, constants.USER_COLLECTION_MAX_NEWS, False)
        # 获取分页数据
        collections = paginate.items
        # 获取当前页
        current_page = paginate.page
        # 获取总页数
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)

    # 收藏列表
    collection_dict_li = []
    for news in collections:
        collection_dict_li.append(news.to_basic_dict())
    data = {
            "total_page": total_page,
            "current_page": current_page,
            "collections": collection_dict_li
        }
    print(total_page, current_page, collection_dict_li)
    return render_template("news/user_collection.html", data=data)


@profile_blu.route("/news_release", methods=["GET", "POST"])
@user_login_data
def news_release():
    categories = []
    try:
        # 获取所有的分类数据
        categories = Category.query.all()
    except Exception as e:
        current_app.logger.error(e)
        # 定义列表保存分类数据
    categories_dicts = []
    for category in categories:
        # 获取字典
        cate_dict = category.to_dict()
        # 拼接内容
        categories_dicts.append(cate_dict)

    # 移除'最新'分类
    categories_dicts.pop(0)
    # 返回内容
    data = {
        "categories": categories_dicts
    }
    if request.method == "GET":
        return render_template("news/user_news_release.html", data=data)

    title = request.form.get("title")
    source = "个人发布"
    digest = request.form.get("digest")
    content = request.form.get("content")
    index_image = request.files.get("index_image")
    category_id = request.form.get("category_id")
    # 1.1 判断数据是否有值
    if not all([title, source, digest, content, index_image]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    # 1.2 尝试读取图片
    try:
        index_image = index_image.read()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数有错误")
    # 2. 将标题图片上传到七牛
    try:
        key = storage(index_image)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.THIRDERR, errmsg="上传图片错误")

    # 3. 初始化新闻模型，并设置相关数据
    news = News()
    news.title = title
    news.digest = digest
    news.source = source
    news.content = content
    news.index_image_url = constants.QINIU_DOMIN_PREFIX + key
    news.category_id = category_id
    news.user_id = g.user.id
    # 1代表待审核状态
    news.status = 1
    # 4.保存到数据库
    print(news.title)
    try:
        db.session.add(news)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
        return jsonify(error=RET.DBERR, errmsg="保存数据失败")
    # 5. 返回结果
    return jsonify(errno=RET.OK, errmsg="发布成功，等待审核")


@profile_blu.route("/news_list")
@user_login_data
def news_list():
    p = request.args.get("p", 1)
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1
    user = g.user
    news_li = []
    total_page = 1
    try:
        paginate = News.query.filter(News.user_id == user.id).paginate(p, constants.USER_COLLECTION_MAX_NEWS, False)
        # 获取当前页数据
        news_li = paginate.items
        # 获取当前页
        current_page = paginate.page
        # 获取总页数
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(error=RET.DBERR, errmsg="保存数据失败")

    news_dict_li = []

    for news_item in news_li:
        news_dict_li.append(news_item.to_review_dict())

    data = {"news_list": news_dict_li,
            "total_page": total_page,
            "current_page": current_page}
    return render_template("news/user_news_list.html", data=data)


@profile_blu.route("/user_follow")
@user_login_data
def user_follow():
    # 獲取頁數
    p = request.args.get("p", 1)
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        p = 1
    user = g.user

    follows = []
    current_page = 1
    total_page = 1
    try:
        paginate = user.followed.paginate(p, constants.USER_FOLLOWED_MAX_COUNT, False)
        # 獲取當前頁數據
        follows = paginate.items
        # 獲取當前頁
        current_page = paginate.page
        # 獲取總頁數
        total_page = paginate.pages
    except Exception as e:
        current_app.logger.error(e)
    user_dict_li = []
    for follow_user in follows:
        user_dict_li.append(follow_user.to_dict())
    data = {
        "users": user_dict_li,
        "total_page": total_page,
        "current_page": current_page
    }
    return render_template("news/user_follow.html", data=data)


@profile_blu.route("/other_info")
@user_login_data
def other_info():
    """查看其他用戶信息"""
    user = g.user
    # 獲取其他用戶id
    user_id = request.args.get("id")
    if not user_id:
        abort(404)
    # 查詢用戶模型
    other = None
    try:
        other = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
    if not other:
        abort(404)

    # 判斷當前用戶是否關注過該用戶
    is_followed = False
    if g.user:
        if other.followers.filter(User.id == user.id).count() > 0:
            is_followed = True
        news_dict_li = list()
        try:
            paginate = News.query.filter(News.user_id == other.id).paginate(1, constants.OTHER_NEWS_PAGE_MAX_COUNT,
                                                                           False)
            news_li = paginate.items
            print(news_li)
            # 獲取當前頁
            current_page = paginate.page
            # 獲取總頁數
            total_page = paginate.pages
        except Exception as e:
            current_app.logger.error(e)
            return jsonify(errno=RET.DBERR, errmsg="數據查詢錯誤")


        for news_item in news_li:
            news_dict_li.append(news_item.to_review_dict())

    # 組織數據，並返回
    data = {
        "user": user.to_dict(),
        "news_list": news_dict_li,
        "user_info": user.to_dict(),
        "other_info": other.to_dict(),
        "is_followed": is_followed
    }
    return render_template("news/other.html", data=data)


@profile_blu.route("/other_news_list")
def other_news_list():
    # 獲取頁數
    p = request.args.get("p", 1)
    user_id = request.args.get("user_id")
    print(p, user_id)
    try:
        p = int(p)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="參數錯誤")
    if not all([p, user_id]):
        return jsonify(errno=RET.PARAMERR, errmsg="參數錯誤")
    try:
        user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="數據查詢錯誤")

    try:
        paginate = News.query.filter(News.user_id == user.id).paginate(p, constants.OTHER_NEWS_PAGE_MAX_COUNT, False)
        news_li = paginate.items
        # 獲取當前頁
        current_page = paginate.page
        # 獲取總頁數
        total_page = paginate.pages
    except Exception as e:
        current_app.loggger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="數據查詢錯誤")

    news_dict_li = list()
    for news_item in news_li:
        news_dict_li.append(news_item.to_review_dict())
    data = {
        "user": user.to_dict(),
        "news_list": news_dict_li,
        "total_page": total_page,
        "current_page": current_page
    }
    print(total_page, current_page)
    return jsonify(errno=RET.OK, errmsg="OK", data=data)


@profile_blu.route("/<int:news_id>")
@user_login_data
def profile_blu_index(news_id):
    user = g.user
    news_list = []
    try:
        news_list = News.query.order_by(News.clicks.desc()).limit(constants.CLICK_RANK_MAX_NEWS)
    except Exception as e:
        current_app.logger.error(e)
    # 定义一个空的字典列表，里面装的就是字典
    news_dict_li = list()
    # 便利对象列表，将对象的字典添加到字典列表中
    for news in news_list:
        news_dict_li.append(news.to_basic_dict())
    # 查询新闻数据
    news = None
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
    if not news:
        # 报404错误，404错误统一显示页面后续再处理
        abort(404)
    # 更新新闻点击次数
    news.clicks += 1
    is_collected = False
    # 如果用户已经登陆
    # 判断用户是否收藏当前新闻，如果收藏：
    if user:
        # collection_news后面可以不用加all, 因为sqlchemy会在使用的时候自动去加载
        if news in user.collection_news:
            is_collected = True

        # 去查询评论数据
        comments = list()
        try:
            comments = Comment.query.filter(Comment.news_id == news_id).order_by(Comment.create_time.desc()).all()
        except Exception as e:
            current_app.logger.error(e)
    comment_like_ids =[]
    comment_dict_li = []
    is_followed = False
    if g.user:
        try:
            # 需求: 查询当前用户在当前新闻里面都点赞了哪些评论
            # 1. 查询出当前新闻的所有评论（［COMMENT］）取到所有的评论id[1, 2, 3, 4, 5]
            comment_ids = [comment.id for comment in comments]
            # 2. 再查询当前评论中哪些评论被当前用户所点赞
            # ([CommentLike])  查询当前comment_id 在第一步的评论id列表内的所有数据
            # &CommentList.user_id = g.user.id
            comment_likes = CommentLike.query.filter(CommentLike.comment_id.in_(comment_ids),
            CommentLike.user_id == g.user.id).all()
            # 3.　取到所有被点赞的评论id 第二步查询出来的是一个
            # [CommentLike] -->[3, 5]
            comment_like_ids = [comment_like.comment_id for comment_like in comment_likes]
        except Exception as e:
            current_app.logger.error(e)

        for comment in comments:
            comment_dict = comment.to_dict()
            # 代表没有点赞
            comment_dict["is_like"] = False
            # 判断当前遍历到的评论是否被当前登陆用户所点赞
            if comment.id in comment_like_ids:
                comment_dict["is_like"] = True
            comment_dict_li.append(comment_dict)

        # if 当前新闻有作者，并且当前登陆用户已经关注过这个用户
        if news.user and user:
            # if user 是否关注过news.user
            if news.user in user.followed:
                is_followed = True
    data = {
        "user": user.to_dict() if user else None,
        "news_dict_li": news_dict_li,
        "news": news.to_dict(),
        "is_collected": is_collected,
        "is_followed": is_followed,
        "comments": comment_dict_li,
    }
    return render_template("news/detail.html", data=data)


@profile_blu.route("/followed_user", methods = ["POST"])
@user_login_data
def followd_user():
    """關注/取消關注用戶"""
    if not g.user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用戶未登錄")
    user_id = request.json.get("user_id")
    action = request.json.get("action")
    print(user_id, action)
    if not all([user_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="參數錯誤")
    if action not in ("follow", "unfollow"):
        return jsonify(errno=RET.PARAMERR, errmsg="參數錯誤")
    # 查詢到關注的用戶信息
    try:
        target_user = User.query.get(user_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.NODATA, errmsg="未查詢到用戶數據")
    # 根據不同操作做出不同邏輯
    if action == "follow":
        if target_user.follows.filter(User.id == g.user.id).count() > 0:
            return jsonify(errno=RET.DATAEXIST, errmsg="當前已關注")
        target_user.followers.append(g.user)
    else:
        if target_user.followers.filter(User.id == g.user.id).count() > 0:
            target_user.followers.remove(g.user)
    # 保存到數據庫
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="數據保存錯誤")
    return jsonify(errno=RET.OK, errmsg="操作成功")

