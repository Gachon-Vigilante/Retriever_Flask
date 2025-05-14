from typing import Optional

from google.cloud import storage
from google.api_core.exceptions import NotFound
import mimetypes


def create_folder(bucket_name, folder_name):
    """ 가상의 폴더를 GCS 버킷에 추가하는 함수 """
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # 빈 파일을 업로드하여 폴더처럼 보이게 함
    blob = bucket.blob(f"{folder_name}/")
    blob.upload_from_string("")  # 빈 파일 업로드

def gcs_file_exists(bucket_name: str, folder_name: str, file_name: str) -> bool:
    """특정 파일이 GCS 버킷에 이미 있는지 확인하는 함수."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # 폴더 포함한 객체 경로 지정
    blob = bucket.blob(f"{folder_name}/{file_name}")

    return blob.exists() # 파일의 존재 여부를 확인해서 반환

def check_gcs_object_and_get_info(bucket_name: str, folder_name: str, file_name: str) -> Optional[dict]:
    """
    GCS 버킷에 특정 객체가 존재하는지 확인하고,
    존재하면 공개 URL과 MIME 타입을 반환한다.

    :param bucket_name: GCS 버킷 이름
    :param folder_name: GCS 폴더 이름
    :param file_name: GCS 파일 이름
    :return: {"url": ..., "content_type": ...} 또는 None
    """
    object_name = f"{folder_name}/{file_name}"
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(object_name)

    try:
        blob.reload()  # 존재 여부 확인
    except NotFound:
        return None

    # MIME 타입 추론 (GCS에 명시된 content_type 또는 파일 확장자로 추정)
    content_type = blob.content_type or mimetypes.guess_type(object_name)[0]

    # 공개 URL 생성 (객체가 공개되어 있어야 함)
    public_url = f"https://storage.googleapis.com/{bucket_name}/{object_name}"

    return {
        "url": public_url,
        "type": content_type or "application/octet-stream"
    }

def upload_bytes_to_gcs(bucket_name, folder_name, file_name, file_bytes, content_type):
    """ 바이트 객체를 GCS 버킷에 추가하는 함수."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # 폴더 포함한 객체 경로 지정
    blob = bucket.blob(f"{folder_name}/{file_name}")

    # 바이트 객체를 GCS에 업로드
    blob.upload_from_string(file_bytes, content_type=content_type)

    # 업로드된 파일의 공개 URL 반환
    return blob.public_url  # https://storage.googleapis.com/{bucket_name}/{folder_name}/{file_name}