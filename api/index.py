from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import base64
import hmac
import hashlib
import time
from pydub import AudioSegment
from io import BytesIO
import os

# Mengimpor library ffmpeg-static untuk mendapatkan path-nya
import ffmpeg_static

# Inisialisasi aplikasi Flask
app = Flask(__name__)
CORS(app)

# Baris ini SANGAT PENTING untuk memberitahu pydub di mana lokasi ffmpeg
# yang sudah dibundel oleh paket ffmpeg-static.
AudioSegment.converter = ffmpeg_static.get_ffmpeg_path()

# Ambil kunci API dari Environment Variables di Vercel
access_key = os.environ.get('ACR_ACCESS_KEY')
access_secret = os.environ.get('ACR_ACCESS_SECRET')
requrl = "http://identify-ap-southeast-1.acrcloud.com/v1/identify"


def find_song_on_deezer(title, artist):
    """Mencari lagu di Deezer untuk mendapatkan sampul album dan URL preview."""
    search_url = "https://api.deezer.com/search"
    params = {"q": f'artist:"{artist}" track:"{title}"'}
    try:
        response = requests.get(search_url, params=params)
        response.raise_for_status()
        data = response.json()
        if data.get('data'):
            track = data['data'][0]
            return {"cover_art": track['album']['cover_medium'], "preview_url": track['preview']}
    except requests.exceptions.RequestException:
        return None

@app.route('/', methods=['POST'])
def identify_song():
    """Endpoint utama untuk menerima file dan mengidentifikasi lagu."""
    if not access_key or not access_secret:
        return jsonify({'success': False, 'message': 'Konfigurasi API di server belum lengkap.'}), 500

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'File tidak ditemukan. Pastikan Anda mengirim file dengan key "file".'}), 400

    uploaded_file = request.files['file']
    
    # Ekstrak audio jika file yang diunggah adalah video
    if uploaded_file.content_type.startswith('video/'):
        try:
            video = AudioSegment.from_file(uploaded_file)
            buf = BytesIO()
            video.export(buf, format='wav')
            audio_sample = buf.getvalue()
        except Exception as e:
            return jsonify({'success': False, 'message': f'Gagal memproses file video: {e}'}), 500
    else:
        audio_sample = uploaded_file.read()

    # Siapkan dan kirim request ke ACRCloud
    sample_bytes = len(audio_sample)
    http_method = "POST"
    http_uri = "/v1/identify"
    data_type = "audio"
    signature_version = "1"
    timestamp = str(time.time())
    string_to_sign = f"{http_method}\n{http_uri}\n{access_key}\n{data_type}\n{signature_version}\n{timestamp}"
    sign = base64.b64encode(
        hmac.new(access_secret.encode('ascii'), string_to_sign.encode('ascii'), digestmod=hashlib.sha1).digest()
    ).decode('ascii')
    
    files = {'sample': audio_sample}
    data = {'access_key': access_key, 'sample_bytes': sample_bytes, 'timestamp': timestamp, 'signature': sign, 'data_type': data_type, "signature_version": signature_version}
    
    response_acr = requests.post(requrl, files=files, data=data)
    result_acr = response_acr.json()

    # Proses respons dari ACRCloud dan cari detail tambahan di Deezer
    status = result_acr.get('status', {})
    if status.get('msg') == 'Success':
        music_info = result_acr.get('metadata', {}).get('music', [{}])[0]
        title = music_info.get('title', 'Tidak Ditemukan')
        artists_list = [artist['name'] for artist in music_info.get('artists', [])]
        artists = ', '.join(artists_list) if artists_list else 'Tidak Diketahui'
        album = music_info.get('album', {}).get('name', 'Tidak Diketahui')
        
        deezer_info = find_song_on_deezer(title, artists_list[0] if artists_list else '')
        
        return jsonify({
            'success': True,
            'title': title,
            'artist': artists,
            'album': album,
            'cover_art': deezer_info['cover_art'] if deezer_info else None,
            'preview_url': deezer_info['preview_url'] if deezer_info else None
        })
    else:
        return jsonify({'success': False, 'message': 'Lagu tidak dapat diidentifikasi.'}), 404
