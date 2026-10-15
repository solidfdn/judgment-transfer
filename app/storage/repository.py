"""Short, retryable storage transactions. Never perform network/model work in callbacks."""
import copy
import fcntl
import json
import os
import tempfile
from pathlib import Path
from core.models import JTError

DELETE = object()

def token(key): return key[0] + '/' + key[1]

class LocalRepository:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.path = self.directory / 'state.json'

    def atomic(self, keys, callback):
        with (self.directory / 'state.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            db = json.loads(self.path.read_text()) if self.path.exists() else {}
            values = {k: copy.deepcopy(db.get(token(k))) for k in keys}
            result = callback(values)
            for k, v in values.items():
                if v is DELETE: db.pop(token(k), None)
                elif v is not None: db[token(k)] = v
            fd, temporary = tempfile.mkstemp(dir=self.directory)
            with os.fdopen(fd, 'w') as file:
                json.dump(db, file, ensure_ascii=False, allow_nan=False)
                file.flush(); os.fsync(file.fileno())
            os.replace(temporary, self.path)
            return copy.deepcopy(result)

    def get(self, kind, identifier):
        return self.atomic([(kind, identifier)], lambda values: values[(kind, identifier)])

    def put(self, kind, identifier, value):
        def write(values): values[(kind, identifier)] = copy.deepcopy(value)
        self.atomic([(kind, identifier)], write)

class FirestoreRepository:
    def __init__(self, project):
        from google.cloud import firestore
        self.client = firestore.Client(project=project)
        self.firestore = firestore

    def ref(self, key): return self.client.collection('jt_' + key[0]).document(key[1])

    def atomic(self, keys, callback):
        keys = list(dict.fromkeys(keys))
        transaction = self.client.transaction(max_attempts=5)
        @self.firestore.transactional
        def run(tx):
            values = {}
            for key in keys:
                snapshot = self.ref(key).get(transaction=tx)
                values[key] = json.loads(snapshot.to_dict()['payload']) if snapshot.exists else None
            original = copy.deepcopy(values)
            result = callback(values)
            for key, value in values.items():
                if value is DELETE:
                    if original[key] is not None: tx.delete(self.ref(key))
                elif value is not None and value != original[key]:
                    data = json.dumps(value, ensure_ascii=False, allow_nan=False)
                    if len(data.encode()) > 850000: raise JTError('INPUT_TOO_LARGE', 'Stored record exceeds the prototype limit.', 413)
                    tx.set(self.ref(key), {'payload': data})
            return result
        return run(transaction)

    def get(self, kind, identifier):
        snapshot = self.ref((kind, identifier)).get()
        return json.loads(snapshot.to_dict()['payload']) if snapshot.exists else None

    def put(self, kind, identifier, value):
        def write(values): values[(kind, identifier)] = value
        self.atomic([(kind, identifier)], write)

class Blobs:
    def __init__(self, directory, bucket=None, project=None):
        self.directory = Path(directory) / 'blobs'
        self.directory.mkdir(parents=True, exist_ok=True)
        self.bucket_name = bucket
        if bucket:
            from google.cloud import storage
            self.bucket = storage.Client(project=project).bucket(bucket)

    def put(self, identifier, data, mime):
        if self.bucket_name:
            self.bucket.blob('sources/' + identifier).upload_from_string(data, content_type=mime, timeout=30)
        else:
            (self.directory / identifier).write_bytes(data)

    def get(self, identifier):
        if self.bucket_name: return self.bucket.blob('sources/' + identifier).download_as_bytes(timeout=30)
        return (self.directory / identifier).read_bytes()

    def uri(self, identifier):
        return 'gs://' + self.bucket_name + '/sources/' + identifier if self.bucket_name else None
