import os
import math
from pathlib import Path

VERSION = '1.0.38'
MODEL = 'gemini-3.5-flash'
LOCATION = 'global'
MODE = os.getenv('JT_MODE', 'MOCK')
PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT', '')
BUCKET = os.getenv('JT_BUCKET', '')
DATA = Path(os.getenv('JT_DATA', '/tmp/jt-data'))
STORE = os.getenv('JT_STORE', 'local')
MAX_COST = float(os.getenv('JT_MODEL_BUDGET_USD', '20'))
INPUT_PRICE = float(os.getenv('JT_INPUT_USD_PER_MILLION', '1.50'))
OUTPUT_PRICE = float(os.getenv('JT_OUTPUT_USD_PER_MILLION', '9.00'))
REQUEST_TIER = os.getenv('JT_REQUEST_TIER', 'standard')
if REQUEST_TIER not in ('standard', 'priority'):
    raise RuntimeError('Unsupported request tier.')
if not all(math.isfinite(x) and x > 0 for x in (MAX_COST, INPUT_PRICE, OUTPUT_PRICE)) or MAX_COST > 100:
    raise RuntimeError('A finite cumulative model budget of at most USD 100 is required.')
if REQUEST_TIER == 'priority' and (INPUT_PRICE, OUTPUT_PRICE) != (2.70, 16.20):
    raise RuntimeError('Priority requires the reviewed Gemini 3.5 Flash prices.')
REQUEST_HEADERS = ({'X-Vertex-AI-LLM-Request-Type': 'shared',
                    'X-Vertex-AI-LLM-Shared-Request-Type': 'priority'}
                   if REQUEST_TIER == 'priority' else {})
CODE_HASH = os.getenv('JT_CODE_HASH', 'local-unpackaged')
SETTINGS = {'model': MODEL, 'location': LOCATION, 'thinking_level': 'LOW',
            'temperature': 'provider_default', 'max_output_tokens': 8192, 'attempts': 2,
            'request_tier': REQUEST_TIER, 'model_window_seconds': 125,
            'call_limit_seconds': 60, 'retry_backoff_seconds': 1,
            'retry_policy': 'one_bounded_transient_retry',
            'first_text_timeout_seconds': 60,
            'decision_transport': 'streamGenerateContent', 'decision_schema_location': 'api_only'}

def secret():
    value = os.getenv('JT_SESSION_SECRET')
    if value: return value
    if MODE == 'LIVE': raise RuntimeError('LIVE requires JT_SESSION_SECRET from Secret Manager.')
    DATA.mkdir(parents=True, exist_ok=True)
    path = DATA / 'local-session-secret'
    if not path.exists():
        import secrets
        path.write_text(secrets.token_hex(32)); path.chmod(0o600)
    return path.read_text()
