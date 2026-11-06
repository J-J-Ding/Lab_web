"""Optional local ClamAV INSTREAM check. Required mode fails closed if scanner unavailable."""
import socket,struct
from django.conf import settings
from rest_framework.exceptions import ValidationError

def check_bytes(data):
    if not settings.FILE_SCAN_REQUIRED:return 'structural_only'
    path=settings.CLAMAV_SOCKET
    if not path or not path.startswith('/'):raise ValidationError({'file':'文件扫描服务未配置，文件不进入可用资产库。'})
    try:
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
            sock.settimeout(10);sock.connect(path);sock.sendall(b'zINSTREAM\0')
            for start in range(0,len(data),65536):
                chunk=data[start:start+65536];sock.sendall(struct.pack('!I',len(chunk))+chunk)
            sock.sendall(struct.pack('!I',0));response=sock.recv(4096)
            if not response.endswith(b'OK\0'):raise ValueError()
    except (OSError,ValueError):raise ValidationError({'file':'文件扫描失败或发现风险，文件不进入可用资产库。'}) from None
    return 'antivirus_clean'
