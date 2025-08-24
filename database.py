import sqlite3

DATABASE = 'database.db'

def init_db():
    with sqlite3.connect(DATABASE) as conn:
        cursor = conn.cursor()
        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                secret_username TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL
            )
        ''')
        # Create katas table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS katas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author_id INTEGER,
                upvotes INTEGER DEFAULT 0,
                saves INTEGER DEFAULT 0,
                completions INTEGER DEFAULT 0,
                difficulty TEXT,
                completion_time TEXT,
                topics_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (author_id) REFERENCES users (id)
            )
        ''')
        # Create topics table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS topics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            )
        ''')
        # Create kata_topics junction table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS kata_topics (
                kata_id INTEGER,
                topic_id INTEGER,
                PRIMARY KEY (kata_id, topic_id),
                FOREIGN KEY (kata_id) REFERENCES katas (id),
                FOREIGN KEY (topic_id) REFERENCES topics (id)
            )
        '''
        )
        # Create user_kata_actions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_kata_actions (
                user_id INTEGER,
                kata_id INTEGER,
                action_type TEXT NOT NULL,
                PRIMARY KEY (user_id, kata_id, action_type),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (kata_id) REFERENCES katas (id)
            )
        '''
        )
        # Create FTS5 table for katas
        cursor.execute('DROP TABLE IF EXISTS katas_fts;')
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS katas_fts USING fts5(title, content, topics_text);
        '''
        )
        # Triggers to keep FTS table in sync with katas table
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS katas_after_insert AFTER INSERT ON katas
            BEGIN
                INSERT INTO katas_fts (rowid, title, content, topics_text) VALUES (new.id, new.title, new.content, new.topics_text);
            END;
        ''')
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS katas_after_delete AFTER DELETE ON katas
            BEGIN
                DELETE FROM katas_fts WHERE rowid = old.id;
            END;
        ''')
        cursor.execute('''
            CREATE TRIGGER IF NOT EXISTS katas_after_update AFTER UPDATE ON katas
            BEGIN
                UPDATE katas_fts SET title = new.title, content = new.content, topics_text = new.topics_text WHERE rowid = new.id;
            END;
        ''')

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn

# Call init_db() when this module is imported to ensure tables are created
init_db()