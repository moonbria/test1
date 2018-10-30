from flask import abort, jsonify
from flask import current_app
from flask import g
from flask import render_template
from flask import request

from info import constants, db
from info.models import News, Comment, CommentLike, User
from info.utils.response_code import RET
from . import detail_blu
from info.utils.common import user_login_data


@detail_blu.route("/<int:news_id>")
@user_login_data
def detail_index(news_id):
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


@detail_blu.route("/news_collect", methods=["POST"])
@user_login_data
def collect_news():
    """
    收藏新闻
    1. 接收参数
    2. 判断参数
    3. 查询新闻，并判断新闻是否存在
    :return:
    """
    user = g.user
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")
    # 1. 接受参数
    news_id = request.json["news_id"]
    print(news_id)
    action = request.json["action"]

    # 2. 判断参数
    if not all([news_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")

    # 3. 查询新闻，并判断新闻是否存在
    try:
        news = News.query.get(news_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库查询错误")
    if not news:
        return jsonify(errno=RET.NODATA, errmsg="未查询到新闻数据")
    # 4.　收藏以及取消收藏
    if action == "cancel_collect":
        if news in user.collection_news:
            user.collection_news.remove(news)
        return jsonify(errno=RET.OK, errmsg="操作成功")
    else:
        if news not in user.collection_news:
            user.collection_news.append(news)
        return jsonify(errno=RET.OK, errmsg="操作成功")


@detail_blu.route("/news_comment", methods=["POST"])
@user_login_data
def comment_news():
    """
    评论新闻或者回复某条新闻下的指定评论
    :return:
    """
    user = g.user
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登录")
    # 1.　取到请求参数
    request_args = request.json
    news_id = request_args["new_id"]
    comment_content = request.json.get("comment")
    parent_id = request_args.get("parent_id")
    print(parent_id)
    # 2. 判断参数
    if not all([news_id, comment_content]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    try:
        news_id=int(news_id)
        if parent_id:
            parent_id = int(parent_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    # 查询新闻，并判断新闻是否存在
    try:
        news = News.query.get(news_id)
    except Exception as e:
        return jsonify(errno=RET.DBERR, errmsg="数据查询错误")
    if not news:
        return jsonify(errno=RET.NODATA, errmsg="未查询到新闻数据")
    # 3. 初始化一个评论模型，并且赋值
    comment = Comment()
    comment.user_id = user.id
    comment.news_id = news_id
    comment.content = comment_content
    if parent_id:
        comment.parent_id = parent_id
    # 添加到数据库
    # 为什么要自己去commit()? 因为return的时候需要用到comment的id
    try:
        db.session.add(comment)
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
        db.session.rollback()
    print(type(comment))
    return jsonify(errno=RET.OK, errmsg="OK", data=comment.to_dict())


@detail_blu.route("/comment_like", methods=["POST"])
@user_login_data
def comment_like():
    """
    评论点赞
    :return:
    """
    user = g.user
    if not user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用户未登陆")
    # 1. 取到请求参数
    comment_id = request.json.get("comment_id")
    action = request.json.get("action")
    # 2. 判断参数
    if not all ([comment_id, action]):
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    if action not in ["add", "remove"]:
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    try:
        comment_id = int(comment_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.PARAMERR, errmsg="参数错误")
    # 3. 获取到要被点赞的评论模型
    try:
        comment = Comment.query.get(comment_id)
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据查询错误")
    if not comment:
        return jsonify(errno=RET.NODATA, errmsg="评论不存在")
    if action == "add":
        comment_like_model = CommentLike.query.filter(
            CommentLike.user_id == user.id, CommentLike.comment_id == comment.id).first()
        if not comment_like_model:
            # 点赞评论
            comment_like_model = CommentLike()
            comment_like_model.user_id = user.id
            comment_like_model.comment_id = comment.id
            db.session.add(comment_like_model)
            # 更新点赞次数
            comment.like_count += 1
    else:
        # 取消点赞评论
        comment_like_model = CommentLike.query.filter(
            CommentLike.user_id == user.id, CommentLike.comment_id == comment.id).first()
        if comment_like_model:
            db.session.delete(comment_like_model)
            # 更新点赞次数
            comment.like_count -= 1
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库操作失败")
    return jsonify(errno=RET.OK, errmsg="OK")


@detail_blu.route("/followed_user", methods = ["POST"])
@user_login_data
def followd_user():
    """關注/取消關注用戶"""
    if not g.user:
        return jsonify(errno=RET.SESSIONERR, errmsg="用戶未登錄")
    user_id = request.json.get("user_id")
    action = request.json.get("action")
    print(action)
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
        if target_user.followers.filter(User.id == g.user.id).count() > 0:
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

