"""Local, versioned correction memory. No model training or external transfer."""
from contextlib import contextmanager
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3
import uuid

from app.models.schemas import FloorPlanData, PlanReview
from app.core.security_context import owner_id


class RevisionConflict(Exception):
    pass


class ProjectRepository:
    def __init__(self, path: str):
        self.path = path
        self.owner_id = owner_id.get()
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS projects (
                    id TEXT PRIMARY KEY, source_hash TEXT NOT NULL,
                    recipe TEXT NOT NULL, source_type TEXT NOT NULL,
                    original TEXT NOT NULL, current TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 0,
                    approved INTEGER NOT NULL DEFAULT 0,
                    measurements_confirmed INTEGER NOT NULL DEFAULT 0,
                    learning_source TEXT, created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    revision INTEGER NOT NULL, before_json TEXT NOT NULL,
                    after_json TEXT NOT NULL, approved INTEGER NOT NULL,
                    allow_learning INTEGER NOT NULL, measurements_confirmed INTEGER NOT NULL,
                    notes TEXT NOT NULL, created_at TEXT NOT NULL,
                    UNIQUE(project_id, revision)
                );
                CREATE INDEX IF NOT EXISTS source_lookup ON projects(source_hash, recipe);
                CREATE TABLE IF NOT EXISTS sources (
                    id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                    name TEXT NOT NULL, sha256 TEXT NOT NULL, role TEXT NOT NULL, content BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS project_owners (
                    project_id TEXT PRIMARY KEY REFERENCES projects(id), user_id TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS owner_lookup ON project_owners(user_id);
                CREATE TABLE IF NOT EXISTS source_details (
                    source_id TEXT PRIMARY KEY REFERENCES sources(id),
                    metadata TEXT NOT NULL
                );
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        try:
            with db:
                yield db
        finally:
            db.close()

    def check_access(self, db, project_id):
        if self.owner_id is not None and not db.execute(
                'SELECT 1 FROM project_owners WHERE project_id=? AND user_id=?',
                (project_id,self.owner_id)).fetchone():
            raise KeyError(project_id)

    def owner_filter(self, alias='p'):
        if self.owner_id is None:return '',()
        return f' AND EXISTS (SELECT 1 FROM project_owners own WHERE own.project_id={alias}.id AND own.user_id=?)',(self.owner_id,)

    def list_projects(self):
        clause,parameters=self.owner_filter()
        with self.connection() as db:
            rows=db.execute('SELECT p.id,p.current,p.revision,p.created_at FROM projects p WHERE 1=1'+clause+
                            ' ORDER BY p.created_at DESC LIMIT 200',parameters).fetchall()
        return [{'project_id':row['id'],'name':json.loads(row['current']).get('architectural_info',{}).get('project_name','Casa sin nombre'),
                 'revision':row['revision'],'created_at':row['created_at']} for row in rows]

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    def create(self, source_hash, recipe, source_type, predicted: FloorPlanData, reuse=True):
        project_id = str(uuid.uuid4())
        clause,parameters=self.owner_filter()
        with self.connection() as db:
            # Consent/review changes and lookup+copy must not race.
            db.execute('BEGIN IMMEDIATE')
            example = db.execute('''
                SELECT r.id, r.after_json FROM reviews r JOIN projects p ON p.id=r.project_id
                WHERE p.source_hash=? AND p.recipe=? AND r.allow_learning=1
                    AND r.approved=1 AND r.measurements_confirmed=1
            '''+clause+' ORDER BY r.created_at DESC LIMIT 1', (source_hash, recipe,*parameters)).fetchone() if reuse else None
            current = FloorPlanData.model_validate_json(example['after_json']) if example else predicted
            db.execute('''INSERT INTO projects
                (id, source_hash, recipe, source_type, original, current, learning_source, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                (project_id, source_hash, recipe, source_type, predicted.model_dump_json(),
                 current.model_dump_json(), example['id'] if example else None, self.now()))
            if self.owner_id is not None:
                db.execute('INSERT INTO project_owners VALUES (?,?)',(project_id,self.owner_id))
        return self.get(project_id)

    def get(self, project_id):
        with self.connection() as db:
            self.check_access(db,project_id)
            row = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
            if row is None:
                raise KeyError(project_id)
            eligible = db.execute('''SELECT COUNT(*) FROM reviews WHERE project_id=?
                AND approved=1 AND measurements_confirmed=1 AND allow_learning=1''', (project_id,)).fetchone()[0]
        return self.public_project(row, eligible)

    @staticmethod
    def public_project(row, eligible):
        return {
            'project_id': row['id'], 'status': 'loaded', 'revision': row['revision'],
            'floor_plan': json.loads(row['current']), 'approved': bool(row['approved']),
            'measurements_confirmed': bool(row['measurements_confirmed']),
            'source': {'sha256': row['source_hash'], 'format': row['source_type'],
                       'import_recipe': json.loads(row['recipe']), 'created_at': row['created_at']},
            'learning': {'mode': 'reviewed_exact_match', 'reused': row['learning_source'] is not None,
                         'example_id': row['learning_source'], 'contributing': bool(eligible),
                         'trained_model': False},
        }

    def review(self, project_id, review: PlanReview):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self.check_access(db,project_id)
            row = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
            if row is None:
                raise KeyError(project_id)
            if row['revision'] != review.base_revision:
                raise RevisionConflict('El proyecto cambió. Recárgalo antes de guardar.')
            revision = row['revision']+1
            # Only the latest reviewed version may be reused; drafts invalidate old examples.
            db.execute('UPDATE reviews SET allow_learning=0 WHERE project_id=?', (project_id,))
            db.execute('''INSERT INTO reviews VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                (str(uuid.uuid4()), project_id, revision, row['current'], review.floor_plan.model_dump_json(),
                 int(review.approved), int(review.allow_learning and review.approved),
                 int(review.measurements_confirmed), review.notes, self.now()))
            db.execute('''UPDATE projects SET current=?, revision=?, approved=?, measurements_confirmed=?
                WHERE id=?''', (review.floor_plan.model_dump_json(), revision, int(review.approved),
                               int(review.measurements_confirmed), project_id))
        return self.get(project_id)

    def revoke(self, project_id):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self.check_access(db,project_id)
            if db.execute('SELECT id FROM projects WHERE id=?', (project_id,)).fetchone() is None:
                raise KeyError(project_id)
            db.execute('UPDATE reviews SET allow_learning=0 WHERE project_id=?', (project_id,))
        return self.get(project_id)

    def stats(self):
        clause,parameters=self.owner_filter()
        with self.connection() as db:
            examples = db.execute('''SELECT COUNT(*) FROM reviews r JOIN projects p ON p.id=r.project_id
                WHERE r.approved=1 AND r.measurements_confirmed=1 AND r.allow_learning=1'''+clause,parameters).fetchone()[0]
            reused = db.execute('SELECT COUNT(*) FROM projects p WHERE p.learning_source IS NOT NULL'+clause,parameters).fetchone()[0]
        return {'mode': 'reviewed_exact_match', 'approved_examples': examples,
                'reused_imports': reused, 'trained_model': False,
                'message': 'Reutiliza revisiones del mismo archivo y configuración dentro de tu cuenta. No generaliza a casas nuevas.'}

    def dataset(self):
        clause,parameters=self.owner_filter()
        with self.connection() as db:
            rows = db.execute('''SELECT r.*, p.source_hash, p.recipe, p.source_type, p.original
                FROM reviews r JOIN projects p ON p.id=r.project_id
                WHERE r.approved=1 AND r.measurements_confirmed=1 AND r.allow_learning=1'''+clause+
                ' ORDER BY r.created_at, r.id',parameters).fetchall()
        return [{'schema_version': 1, 'example_id': r['id'], 'source_sha256': r['source_hash'],
                 'recipe': json.loads(r['recipe']), 'source_type': r['source_type'],
                 'predicted': json.loads(r['original']), 'corrected': json.loads(r['after_json']),
                 'reviewed_at': r['created_at'], 'units': 'm'} for r in rows]

    def add_source(self, project_id, name, digest, role, content, metadata=None):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self.check_access(db,project_id)
            if db.execute('SELECT id FROM projects WHERE id=?', (project_id,)).fetchone() is None:
                raise KeyError(project_id)
            duplicate=db.execute('SELECT id FROM sources WHERE project_id=? AND sha256=?',(project_id,digest)).fetchone()
            if duplicate:
                pass  # Classification changes use describe_source; re-uploading is idempotent.
            else:
                size = db.execute('SELECT COALESCE(SUM(length(content)),0) FROM sources WHERE project_id=?', (project_id,)).fetchone()[0]
                if size+len(content) > 100*1024*1024:
                    raise ValueError('Máximo de 100 MB de fuentes por proyecto')
                source_id=str(uuid.uuid4())
                db.execute('INSERT INTO sources VALUES (?, ?, ?, ?, ?, ?)',
                    (source_id, project_id, name, digest, role, content))
                if metadata is not None:
                    db.execute('INSERT INTO source_details VALUES (?,?)',(source_id,json.dumps(metadata)))
        return self.sources(project_id)

    def sources(self, project_id, include_content=False):
        project=self.get(project_id)
        fields = '*' if include_content else 'id, name, sha256, role, length(content) AS size_bytes'
        with self.connection() as db:
            self.check_access(db,project_id)
            rows=[dict(row) for row in db.execute(f'SELECT {fields} FROM sources WHERE project_id=? ORDER BY rowid', (project_id,))]
            details={r['source_id']:json.loads(r['metadata']) for r in db.execute(
                'SELECT d.* FROM source_details d JOIN sources s ON s.id=d.source_id WHERE s.project_id=?',(project_id,))}
        return [{**row,'metadata':details.get(row['id'],
            {'document_type':'floor_plan','page':project['source']['import_recipe'].get('page',1)}
            if row['role']=='original' else {})} for row in rows]

    def source(self, project_id, source_id):
        with self.connection() as db:
            self.check_access(db,project_id)
            row=db.execute('SELECT * FROM sources WHERE project_id=? AND id=?',(project_id,source_id)).fetchone()
            if row is None:raise KeyError(source_id)
            detail=db.execute('SELECT metadata FROM source_details WHERE source_id=?',(source_id,)).fetchone()
        return {**dict(row),'metadata':json.loads(detail['metadata']) if detail else {}}

    def describe_source(self, project_id, source_id, metadata):
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            self.check_access(db,project_id)
            if db.execute('SELECT id FROM sources WHERE project_id=? AND id=?',(project_id,source_id)).fetchone() is None:
                raise KeyError(source_id)
            db.execute('INSERT OR REPLACE INTO source_details VALUES (?,?)',(source_id,json.dumps(metadata)))
        return self.sources(project_id)

    def history(self, project_id):
        self.get(project_id)
        with self.connection() as db:
            self.check_access(db,project_id)
            rows = db.execute('SELECT * FROM reviews WHERE project_id=? ORDER BY revision', (project_id,)).fetchall()
        return [{**{k: r[k] for k in ('id', 'revision', 'approved', 'allow_learning', 'measurements_confirmed', 'notes', 'created_at')},
                 'before': json.loads(r['before_json']), 'after': json.loads(r['after_json'])} for r in rows]

    def original_source(self, project_id):
        self.get(project_id)
        with self.connection() as db:
            self.check_access(db,project_id)
            row=db.execute("SELECT name,sha256,content FROM sources WHERE project_id=? AND role='original' ORDER BY rowid LIMIT 1",(project_id,)).fetchone()
        return dict(row) if row else None

    def archive_snapshot(self, project_id, include_content=True):
        with self.connection() as db:
            db.execute('BEGIN')
            self.check_access(db,project_id)
            row = db.execute('SELECT * FROM projects WHERE id=?', (project_id,)).fetchone()
            if row is None:
                raise KeyError(project_id)
            reviews = db.execute('SELECT * FROM reviews WHERE project_id=? ORDER BY revision', (project_id,)).fetchall()
            fields = '*' if include_content else 'id, name, sha256, role, length(content) AS size_bytes'
            sources = [dict(source) for source in db.execute(f'SELECT {fields} FROM sources WHERE project_id=? ORDER BY rowid', (project_id,))]
            details={r['source_id']:json.loads(r['metadata']) for r in db.execute(
                'SELECT d.* FROM source_details d JOIN sources s ON s.id=d.source_id WHERE s.project_id=?',(project_id,))}
            sources=[{**s,'metadata':details.get(s['id'],{})} for s in sources]
            eligible = any(r['approved'] and r['measurements_confirmed'] and r['allow_learning'] for r in reviews)
        history = [{**{k:r[k] for k in ('id','revision','approved','allow_learning','measurements_confirmed','notes','created_at')},
                    'before':json.loads(r['before_json']), 'after':json.loads(r['after_json'])} for r in reviews]
        return self.public_project(row, eligible), json.loads(row['original']), history, sources
