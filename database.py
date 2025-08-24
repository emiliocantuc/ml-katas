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
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author_id INTEGER,
                upvotes INTEGER DEFAULT 0,
                saves INTEGER DEFAULT 0,
                completions INTEGER DEFAULT 0,
                difficulty TEXT,
                completion_time TEXT,
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
                kata_id TEXT,
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
                kata_id TEXT,
                action_type TEXT NOT NULL,
                PRIMARY KEY (user_id, kata_id, action_type),
                FOREIGN KEY (user_id) REFERENCES users (id),
                FOREIGN KEY (kata_id) REFERENCES katas (id)
            )
        '''
        )
        # Create FTS5 table for katas
        cursor.execute('''
            CREATE VIRTUAL TABLE IF NOT EXISTS katas_fts USING fts5(title, content, topics_text, content='katas', content_rowid='id');
        '''
        )
        conn.commit()

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn

# Call init_db() when this module is imported to ensure tables are created
init_db()