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
import yt_dlp
import uuid

app = Flask(__name__)
CORS(app)

# Mengambil kunci API dari Environment Variables di Vercel
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

def identify_audio_sample(audio_sample):
    """Fungsi terpusat untuk proses identifikasi ke ACRCloud."""
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
    return response_acr.json()

@app.route('/', methods=['POST'])
def identify_from_file():
    """Endpoint untuk handle upload file."""
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'File tidak ditemukan.'}), 400

    uploaded_file = request.files['file']
    
    try:
        if uploaded_file.content_type.startswith('video/'):
            video = AudioSegment.from_file(uploaded_file)
            buf = BytesIO()
            video.export(buf, format='wav')
            audio_sample = buf.getvalue()
        else:
            audio_sample = uploaded_file.read()
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error saat memproses file: {e}'}), 500


    result_acr = identify_audio_sample(audio_sample)
    
    status = result_acr.get('status', {})
    if status.get('msg') == 'Success':
        music_info = result_acr.get('metadata', {}).get('music', [{}])[0]
        title = music_info.get('title', 'Tidak Ditemukan')
        artists_list = [artist['name'] for artist in music_info.get('artists', [])]
        artists = ', '.join(artists_list) if artists_list else 'Tidak Diketahui'
        album = music_info.get('album', {}).get('name', 'Tidak Diketahui')
        deezer_info = find_song_on_deezer(title, artists_list[0] if artists_list else '')
        return jsonify({ 'success': True, 'title': title, 'artist': artists, 'album': album, 'cover_art': deezer_info['cover_art'] if deezer_info else None, 'preview_url': deezer_info['preview_url'] if deezer_info else None })
    else:
        return jsonify({'success': False, 'message': 'Lagu tidak dapat diidentifikasi.'}), 404

@app.route('/identify-by-url', methods=['POST'])
def identify_from_url():
    """Endpoint untuk handle submit URL."""
    data = request.get_json()
    url = data.get('url')
    if not url:
        return jsonify({'success': False, 'message': 'URL tidak ditemukan.'}), 400

    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        response = requests.head(url, allow_redirects=True, timeout=10, headers=headers)
        expanded_url = response.url
    except requests.exceptions.RequestException as e:
        return jsonify({'success': False, 'message': f'Gagal mendapatkan URL asli dari link pendek: {e}'}), 500

    temp_filename = f"/tmp/{uuid.uuid4()}.mp3"
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': temp_filename,
        'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}],
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([expanded_url])

        with open(temp_filename, 'rb') as f:
            audio_sample = f.read()

        result_acr = identify_audio_sample(audio_sample)
    finally:
        if os.path.exists(temp_filename):
            os.remove(temp_filename)

    status = result_acr.get('status', {})
    if status.get('msg') == 'Success':
        music_info = result_acr.get('metadata', {}).get('music', [{}])[0]
        title = music_info.get('title', 'Tidak Ditemukan')
        artists_list = [artist['name'] for artist in music_info.get('artists', [])]
        artists = ', '.join(artists_list) if artists_list else 'Tidak Diketahui'
        album = music_info.get('album', {}).get('name', 'Tidak Diketahui')
        deezer_info = find_song_on_deezer(title, artists_list[0] if artists_list else '')
        return jsonify({ 'success': True, 'title': title, 'artist': artists, 'album': album, 'cover_art': deezer_info['cover_art'] if deezer_info else None, 'preview_url': deezer_info['preview_url'] if deezer_info else None })
    else:
        return jsonify({'success': False, 'message': 'Lagu tidak dapat diidentifikasi dari URL ini.'}), 404
