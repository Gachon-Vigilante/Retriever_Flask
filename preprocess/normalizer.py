from charset_normalizer import detect

def to_utf8(html_text):
    """HTML 텍스트를 UTF-8 인코딩으로 변환합니다.

    Args:
        html_text: 변환할 HTML 텍스트

    Returns:
        bytes: UTF-8로 인코딩된 HTML 텍스트

    Raises:
        ValueError: 인코딩을 감지할 수 없는 경우
    """
    detected = detect(html_text)
    encoding = detected.get('encoding')
    if not encoding:
        raise ValueError("인코딩을 감지할 수 없습니다.")
    return html_text.decode(encoding).encode('utf-8')
