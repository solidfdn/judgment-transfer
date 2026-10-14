import io
import json
import re
import subprocess
import tempfile
from pathlib import Path
from PIL import Image
from pypdf import PdfReader
from pypdf.errors import PyPdfError
from core.models import JTError, digest

LIMITS = {'.txt': (1*1024**2, 'text/plain'), '.pdf': (5*1024**2, 'application/pdf'), '.png': (2*1024**2, 'image/png'), '.jpg': (2*1024**2, 'image/jpeg'), '.jpeg': (2*1024**2, 'image/jpeg'), '.mp4': (10*1024**2, 'video/mp4')}

def inspect_file(name, data, declared_mime=None):
    extension = Path(name).suffix.lower()
    if extension not in LIMITS: raise JTError('INVALID_INPUT', 'Supported files: TXT, text PDF, PNG, JPEG and MP4.')
    limit, mime = LIMITS[extension]
    if not data or len(data) > limit: raise JTError('INPUT_TOO_LARGE', 'This file is empty or exceeds its size limit.', 413)
    if declared_mime and declared_mime not in (mime, 'application/octet-stream'):
        raise JTError('INVALID_INPUT', 'Filename, MIME type and file contents must agree.')
    metadata = {'name': Path(name).name[:160], 'mime': mime, 'size': len(data), 'version_hash': digest(data), 'pages': 0, 'duration': 0}
    try:
        if extension == '.txt':
            text = data.decode('utf-8-sig')
            if '\x00' in text: raise ValueError('Binary data')
            metadata['lines'] = max(1, len(text.splitlines()))
        elif extension == '.pdf':
            if not data.startswith(b'%PDF-'): raise ValueError('PDF signature')
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted or not 1 <= len(reader.pages) <= 10: raise ValueError('PDF pages/encryption')
            text = '\n'.join(page.extract_text() or '' for page in reader.pages)
            if not text.strip(): raise ValueError('Only text PDFs are supported')
            metadata['pages'] = len(reader.pages)
        elif mime.startswith('image/'):
            image = Image.open(io.BytesIO(data))
            if image.format != ('PNG' if extension == '.png' else 'JPEG') or image.width * image.height > 16000000: raise ValueError('Image format or size')
            image.verify(); text = ''
        else:
            if len(data) < 12 or data[4:8] != b'ftyp': raise ValueError('MP4 signature')
            with tempfile.NamedTemporaryFile(suffix='.mp4') as f:
                f.write(data); f.flush()
                r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration:stream=codec_type', '-of', 'json', f.name], capture_output=True, timeout=8, check=True)
            details = json.loads(r.stdout)
            duration = float(details['format']['duration'])
            if not 0 < duration <= 60 or not any(x['codec_type'] == 'video' for x in details['streams']): raise ValueError('Video duration')
            metadata['duration'] = duration; text = ''
    except (ValueError, UnicodeError, OSError, subprocess.SubprocessError, KeyError, PyPdfError, Image.DecompressionBombError) as e:
        raise JTError('INVALID_INPUT', 'File contents are invalid for this type: ' + type(e).__name__)
    return metadata, text

def text_for(source, blobs):
    if source['mime'] == 'text/plain': return blobs.get(source['blob_id']).decode('utf-8-sig')
    if source['mime'] == 'application/pdf':
        return '\n'.join(f'[page:{i+1}]\n' + (p.extract_text() or '') for i, p in enumerate(PdfReader(io.BytesIO(blobs.get(source['blob_id']))).pages))
    return ''

def validate_ref(reference, source, blobs):
    if not source or source['version_hash'] != reference['version_hash']:
        raise JTError('INVALID_INPUT', 'Unknown evidence or stale source hash.')
    locator, quote = reference['locator'], reference['quote']
    text = text_for(source, blobs)
    if source.get('human'):
        valid = locator == 'human:1'
    elif source['mime'] == 'text/plain':
        match = re.fullmatch(r'line:(\d+)(?:-(\d+))?', locator)
        valid = bool(match) and 1 <= int(match[1]) <= int(match[2] or match[1]) <= source['lines']
        if valid: text = '\n'.join(text.splitlines()[int(match[1])-1:int(match[2] or match[1])])
    elif source['mime'] == 'application/pdf':
        match = re.fullmatch(r'page:(\d+)', locator)
        valid = bool(match) and 1 <= int(match[1]) <= source['pages']
        if valid: text = PdfReader(io.BytesIO(blobs.get(source['blob_id']))).pages[int(match[1])-1].extract_text() or ''
    elif source['mime'].startswith('image/'):
        valid = locator == 'image:1' and quote == ''
    else:
        match = re.fullmatch(r'seconds:(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)', locator)
        valid = bool(match) and 0 <= float(match[1]) < float(match[2]) <= source['duration'] and quote == ''
    if not valid or quote and quote not in text:
        raise JTError('INVALID_INPUT', 'Evidence location or quotation is invalid.')
