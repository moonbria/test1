import random
import re

import datetime
from flask import current_app, jsonify
from flask import make_response
from flask import request
from flask import session

from info import constants, db
from info import redis_store
from info.lib.yuntongxun.sms import CCP
from info.utils.captcha.captcha import captcha
from info.utils.response_code import RET
from info.modules.passport import passport_blu
from info.models import User


@passport_blu.route("/smscode", methods=["POST", "GET"])
def send_sms():
    """
    1.接收参数并判断是否有值
    2.校验手机号是否正确
    3.通过传入的图片编码去redis中查询真实的图片验证码内容
    4.进行验证码内容的比对
    5.生成发送短信的内容并发送短信
    6.redis中保存短信验证码内容
    7.返回发送成功的响应
    :return:
    """
    args_data = request.json
    # mobile = args_data.get("mobile")
    mobile = "17775606518"
    image_code = args_data.get("image_code")
    image_code_id = args_data.get("image_code_id")
    if not all([mobile, image_code, image_code_id]):
        return jsonify(errno=RET.PARAMERR, errmsg = "参数不全")
    if not re.match("^1[3578][0-9]{9}$", mobile):
        return jsonify(errno=RET.PARAMERR, errmsg = "手机号不正确")
    try:
        real_image_code = redis_store.get("ImageCode_" + image_code_id)
        print(real_image_code, "real_image_code")
        # 如果能够取出值来，删除redis中缓存的内容
        if real_image_code:
            real_image_code = real_image_code
            redis_store.delete("ImageCode_" + image_code_id)
    except Exception as e:
        current_app.logger.error(e)
        # 获取图片验证码失败
        return jsonify(errno=RET.DBERR, errmsg="获取图片验证码失败")
    # 3.1 判断验证码是否存在，已过期
    if not real_image_code:
        # 验证码已过期
        return jsonify(errno=RET.NODATA, errmsg="验证码已过期")
    # 4.进行验证码内容的比对
    if image_code.lower() == real_image_code.lower(): # 测试中
        return jsonify(errno=RET.DATAERR, errmsg="验证码输入错误")
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="数据库查询错误")
    if user:
        #　该手机已经被注册
        return jsonify(errno=RET.DATAEXIST, errmsg="该手机已经被注册")
    # 5.生成发送短信的内容病发送短信
    result = random.randint(0, 999999)
    sms_code = "%06d" % result
    current_app.logger.debug("短信验证码的内容：%s" % sms_code)
    # result = CCP().send_template_sms(mobile, [sms_code, constants.SMS_CODE_REDIS_EXPIRES / 60], "1")
    # if result != 0:
    #     # 发送短信失败
    #     return jsonify(errno=RET.THIRDERR, errmsg="发送短信失败")
    # redis中保存短信验证码中的内容
    try:
        redis_store.set("SMS_" + mobile, sms_code, constants.SMS_CODE_REDIS_EXPIRES)
        print(mobile, "SMS_SET")
    except Exception as e:
        current_app.logger.error(e)
        # 保存短信验证码失败
        return jsonify(errno=RET.DBERR, errmsg="保存短信验证码失败")
    # 返回发送成功的响应
    return jsonify(errno=RET.OK, errmsg="发送成功")


@passport_blu.route("/logout")
def logout():
    # pop是移除session中的

    session.pop("user_id", None)
    session.pop("mobile", None)
    session.pop("nick_name", None)
    return jsonify(errno=RET.OK, errmsg="退出成功")



@passport_blu.route("/login", methods=["POST"])
def login():
    """
    1. 获取参数和判断是否有值
    2. 从数据库查询出指定的用户
    3. 校验密码
    4. 保存用户登陆状态
    5. 保存用户登陆状态
    6. 返回结果
    :return:
    """
    # 1. 获取参数和判断是否有值
    json_data = request.json
    # mobile = json_data.get("mobile")
    mobile = "17775606517"
    # passport = json_data.get("password")
    passport = "123456"
    if not all([mobile, passport]):
        # 参数不全
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")
    # 2. 从数据库查询出指定的用户
    try:
        user = User.query.filter_by(mobile=mobile).first()
    except Exception as e:
        current_app.logger.error(e)
        return jsonify(errno=RET.DBERR, errmsg="查询数据错误")
    if not user:
        return jsonify(errno=RET.USERERR, errmsg="用户不存在")
    # 3.校验密码
    if not user.check_password(passport):
        return jsonify(errno=RET.PWDERR, errmsg="密码错误")

    #4. 保存用户登陆状态
    session["user_id"] = user.id
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile
    # 记录用户最后一次登陆时间
    user.last_login = datetime.datetime.now()
    try:
        db.session.commit()
    except Exception as e:
        current_app.logger.error(e)
    # 5. 登陆成功
    # 如果在视图函数中，对模型身上的属性有修改，那么需要commit到数据库
    # 其实可以不用自己去写，如果对db.session.commit()先进行了配置
    # SQLALCHEMY_COMMIT_ON_TEARDOWN = True
    # 但是这样就没有rollback
    return jsonify(errno=RET.OK, errmsg="OK")



@passport_blu.route("/register", methods=["POST"])
def register():
    """
    获取参数和判断是否有值
    从redis中获取指定手机号对应的短信验证码
    校验验证码
    初始化user模型，设置数据并添加到数据库
    保存当前用户的状态
    返回注册的结果
    :return:
    """
    # 1. 获取参数和判断是否有值
    json_data = request.json
    # mobile = json_data.get("mobile")
    mobile = "17775606517"
    sms_code = json_data.get("smscode")
    password = json_data.get("password")
    print(mobile, "MObile")

    if not all([mobile, sms_code, password]):
        # 参数不全
        return jsonify(errno=RET.PARAMERR, errmsg="参数不全")
        # 从redis中获取指定手机号对应的短信验证码
    try:
        real_sms_code = redis_store.get("SMS_" + mobile)
        print(real_sms_code, "real_sms_code")
    except Exception as e:
        current_app.logger.error(e)
        # 获取本地验证码失败
        return jsonify(errno=RET.DBERR, errmsg="获取本地验证码失败")

    # if not real_sms_code:
    #     # 短信验证码过期
    #     return jsonify(errno=RET.NODATA, errmsg="短信验证码过期")
    #     # 删除短信验证码
    try:
        redis_store.delete("SMS_" + mobile)
    except Exception as e:
        current_app.logger.error(e)
        # 初始化user模型，　设置数据并添加到数据库
    user = User()
    user.nick_name = mobile
    user.mobile = mobile
    # 对密码进行处理
    user.password = password
    user.last_login = datetime.datetime.now()
    # try:
    #     db.session.add(user)
    #     db.session.commit()
    # except Exception as e:
    #     db.session.rollback()
    #     current_app.logger.error(e)
    #     # 数据保存错误
    #     return jsonify(errno=RET.DATAERR, errmsg="数据保存错误")
    # 保存用户登陆状态
    session["user_id"] = user.id
    session["nick_name"] = user.nick_name
    session["mobile"] = user.mobile

    # 返回注册结果
    print("运行到结尾")
    return jsonify(errno=RET.OK, errmsg="OK")



@passport_blu.route('/image_code')
def get_iamge_code():
    print("1", "get_image_code")
    """获取图片验证码"""
    # 1.获取当前图片编号ｉｄ
    code_id = request.args.get("code_id")
    # 2.生成验证码
    name, text, image = captcha.generate_captcha()
    try:
        # 保存当前生成的图片验证码内容
        redis_store.setex("ImageCode_" + code_id, constants.IMAGE_CODE_REDIS_EXPIRES, text)
    except Exception as e:
        current_app.logger.error(e)
        return make_response(jsonify(errno = RET.DATAERR, errmsg = "保存图片验证码失败"))
    # 返回响应内容
    resp = make_response(image)
    # 设置内容类型
    # 不然默认text/file 浏览器可能无法识别
    resp.headers["Content_Type"] = "image/jpg"
    return resp