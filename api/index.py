from flask import Flask, jsonify
from flask_cors import CORS

# Inisialisasi aplikasi Flask
app = Flask(__name__)
CORS(app)

# Endpoint ini akan menangkap SEMUA request ke path manapun
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def health_check(path):
    """Endpoint 'Tes Kesehatan' untuk memastikan server berjalan."""
    return jsonify({
        "status": "OK",
        "message": "Selamat! Server Flask Anda berjalan di Vercel.",
        "requested_path": f"/{path}"
    }), 200
