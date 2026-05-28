import base64
import httpx

BASE = 'http://localhost:8000'

print('Requesting /api/tts to generate test audio...')
resp = httpx.post(f'{BASE}/api/tts', json={'text': 'Hello this is a test for speech to text.', 'voice': 'en-US-Journey-F'}, timeout=30.0)
print('TTS status', resp.status_code)
print(resp.text[:200])
resp.raise_for_status()
obj = resp.json()
audio_b64 = obj['audio_b64']
with open('test_stt.mp3', 'wb') as f:
    f.write(base64.b64decode(audio_b64))
print('Saved test_stt.mp3')

with open('test_stt.mp3', 'rb') as f:
    files = {'audio': ('test_stt.mp3', f, 'audio/mpeg')}
    resp2 = httpx.post(f'{BASE}/api/stt', files=files, timeout=60.0)
    print('STT status', resp2.status_code)
    print(resp2.text)
