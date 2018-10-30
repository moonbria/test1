import logging
from qiniu import Auth, put_data

# 需要填写你的 Access Key 和 Secret Key
access_key = 'EX30k_FY9E2qF7rg8pgMss00XitrS5GmIN2wIQru'
secret_key = 'RFym2r0hV_jqGs6piaGyGkcsVA_Z6wZTocYexbS8'

# 要上传的空间
bucket_name = 'hyp1112'


def storage(data):
    """骑牛云存储上传文件接口"""
    if not data:
        return None
    try:
        # 构建鉴权对象
        q = Auth(access_key, secret_key)
        # 生成上传Token, 可以指定过期时间等
        token = q.upload_token(bucket_name)

        # 上传文件
        ret, info = put_data(token, None, data)
    except Exception as e:
        logging.error(e)
        raise e
    if info and info.status_code != 200:
        raise Exception("上传文件到七牛失败")
    # 返回七牛中保存的图片名，这个图片名也是访问七牛获得图片的路径
    return ret["key"]

if __name__ == '__main__':
    file_name = input("请输入上传的文件")
    with open(file_name, "rb") as f:
        storage(f.read())
