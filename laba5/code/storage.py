from flask import Flask, request, send_file, jsonify, abort
import logging
import os
import shutil
from datetime import datetime
from http import HTTPStatus
from werkzeug.exceptions import HTTPException

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STORAGE_DIR = os.path.join(BASE_DIR, 'storage')
os.makedirs(STORAGE_DIR, exist_ok=True)


def normalize_path(path: str) -> str:
    path = (path or '').lstrip('/')
    normalized = os.path.normpath(path)
    if normalized in ('.', ''):
        return ''
    if normalized.startswith('..') or os.path.isabs(normalized):
        abort(400, 'Invalid path')
    return normalized


def get_full_path(path: str) -> str:
    safe_path = normalize_path(path)
    full_path = os.path.abspath(os.path.join(STORAGE_DIR, safe_path))
    if not full_path.startswith(STORAGE_DIR):
        abort(400, 'Path traversal detected')
    return full_path


def list_directory(full_path: str):
    if not os.path.exists(full_path):
        abort(404, 'Directory not found')
    if not os.path.isdir(full_path):
        abort(400, 'Not a directory')

    entries = []
    for name in sorted(os.listdir(full_path)):
        entry_path = os.path.join(full_path, name)
        stat = os.stat(entry_path)
        entries.append({
            'name': name,
            'type': 'directory' if os.path.isdir(entry_path) else 'file',
            'size': stat.st_size,
            'modified': datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })
    return entries


@app.errorhandler(HTTPException)
def handle_http_exception(error):
    response = jsonify({'error': error.description})
    response.status_code = error.code
    return response


@app.route('/', methods=['GET'])
def get_root():
    return jsonify({'path': '', 'entries': list_directory(STORAGE_DIR)})


@app.route('/upload/<path:file_path>', methods=['POST'])
def upload_file(file_path):
    full_path = get_full_path(file_path)

    if 'file' not in request.files:
        abort(400, 'No file provided')

    file = request.files['file']
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    file.save(full_path)

    return jsonify({'path': file_path, 'status': 'uploaded'}), 201


@app.route('/<path:file_path>', methods=['GET', 'PUT', 'DELETE', 'HEAD'])
def handle_path(file_path):
    full_path = get_full_path(file_path)

    if request.method == 'GET':
        if os.path.isdir(full_path):
            return jsonify({'path': file_path, 'entries': list_directory(full_path)})
        if os.path.isfile(full_path):
            return send_file(full_path, as_attachment=False)
        abort(404, 'File or directory not found')

    if request.method == 'HEAD':
        if not os.path.isfile(full_path):
            abort(404, 'File not found')
        stat = os.stat(full_path)
        response = app.response_class()
        response.headers['Content-Length'] = str(stat.st_size)
        response.headers['Last-Modified'] = datetime.fromtimestamp(stat.st_mtime).strftime('%a, %d %b %Y %H:%M:%S GMT')
        return response

    if request.method == 'PUT':
        if 'X-Copy-From' in request.headers:
            source_path = request.headers.get('X-Copy-From', '')
            source_full = get_full_path(source_path)
            if not os.path.exists(source_full) or not os.path.isfile(source_full):
                abort(404, 'Source file not found')
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            shutil.copy2(source_full, full_path)
            return jsonify({'path': file_path, 'status': 'copied'}), 201

        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'wb') as f:
            f.write(request.get_data())
        return jsonify({'path': file_path, 'status': 'created'}), 201

    if request.method == 'DELETE':
        if not os.path.exists(full_path):
            abort(404, 'File or directory not found')
        if os.path.isdir(full_path):
            shutil.rmtree(full_path)
        else:
            os.remove(full_path)
        return '', 204


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=50001, debug=True)
