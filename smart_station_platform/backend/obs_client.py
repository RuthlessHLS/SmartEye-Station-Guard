from obs import ObsClient
from django.conf import settings

def get_obs_client():
    return ObsClient(
        access_key_id=settings.OBS_ACCESS_KEY_ID,
        secret_access_key=settings.OBS_SECRET_ACCESS_KEY,
        server=settings.OBS_ENDPOINT
    )

def upload_to_obs(local_file, obs_key):
    """
    上传本地文件到华为云OBS
    :param local_file: 本地文件路径
    :param obs_key: OBS桶内目标文件名（含路径）
    :return: True/False
    """
    client = get_obs_client()
    resp = client.putFile(settings.OBS_BUCKET_NAME, obs_key, local_file)
    return resp.status < 300

def download_from_obs(obs_key, local_file):
    """
    从华为云OBS下载文件到本地
    :param obs_key: OBS桶内文件名（含路径）
    :param local_file: 本地保存路径
    :return: True/False
    """
    client = get_obs_client()
    resp = client.getObject(settings.OBS_BUCKET_NAME, obs_key, downloadPath=local_file)
    return resp.status < 300