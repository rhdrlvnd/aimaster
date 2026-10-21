import os
import subprocess
import tempfile
import threading
from pathlib import Path
from pptx import Presentation
from io import BytesIO

RENDER_LOCK = threading.Lock()
MAX_SLIDES = 20


def render_slides(data, destination):
    count = len(Presentation(BytesIO(data)).slides)
    if not 1 <= count <= MAX_SLIDES:
        raise ValueError('PPT는 1~20장까지 등록할 수 있습니다.')
    if os.name != 'nt':
        raise ValueError('현재 PPT 이미지 변환은 PowerPoint가 설치된 Windows에서 지원합니다.')
    destination.mkdir(parents=True, exist_ok=True)
    with RENDER_LOCK, tempfile.TemporaryDirectory(prefix='handover-ppt-') as folder:
        source = Path(folder) / 'source.pptx'
        source.write_bytes(data)
        try:
            subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-File',
                str(Path(__file__).with_name('render_ppt.ps1')), '-SourcePath', str(source),
                '-OutputPath', str(destination.resolve())], check=True, capture_output=True,
                timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
        except (subprocess.SubprocessError, OSError) as error:
            raise ValueError('PPT 이미지 변환에 실패했습니다. PowerPoint 설치·문서 암호·파일 상태를 확인해 주세요.') from error
    if any(not (destination / f'{i}.png').is_file() for i in range(1, count+1)):
        raise ValueError('일부 슬라이드를 변환하지 못했습니다. 문서는 등록되지 않았습니다.')
    if sum(p.stat().st_size for p in destination.glob('*.png')) > 20 * 1024 * 1024:
        raise ValueError('슬라이드 이미지가 20MB를 초과합니다. PPT를 나누어 등록해 주세요.')
    return count
