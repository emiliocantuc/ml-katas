# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "blinker",
#     "click",
#     "flask",
#     "latex2mathml",
#     "markdown2",
# ]
# ///
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, g
import markdown2
import uuid
import re
from database import get_db, init_db, DATABASE
import os
import sqlite3
import json

KATAS_PER_PAGE = 20
ALLOWED_COMPLETION_TIMES = ['<10 mins', '<30 mins', '<1 hr', '>1 hr']
ALLOWED_DIFFICULTIES = ['easy', 'medium', 'hard']


app = Flask(__name__)
app.secret_key = 'supersecretkey'

# Initialize the database when the app starts
with app.app_context():
    init_db()

# Function to close the database connection at the end of the request
@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

# Helper function to get the current user from the database
def get_current_user():
    secret_username = session.get('username')
    if secret_username:
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE secret_username = ?", (secret_username,))
        user = cursor.fetchone()
        return user
    return None

# Helper function to get a kata by ID
def get_kata_by_id(kata_id, user_id=None):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT k.*, u.display_name as author_display_name FROM katas k JOIN users u ON k.author_id = u.id WHERE k.id = ?", (kata_id,))
    kata = cursor.fetchone()
    if kata:
        # Fetch topics for the kata
        cursor.execute("SELECT t.name FROM topics t JOIN kata_topics kt ON t.id = kt.topic_id WHERE kt.kata_id = ?", (kata_id,))
        topics = [row['name'] for row in cursor.fetchall()]
        kata_dict = dict(kata)
        kata_dict['topics'] = topics
        kata_dict['author_id'] = kata['author_display_name'] # Use display name

        if user_id:
            cursor.execute("SELECT 1 FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'upvote'", (user_id, kata_id))
            kata_dict['is_upvoted'] = cursor.fetchone() is not None
            cursor.execute("SELECT 1 FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'save'", (user_id, kata_id))
            kata_dict['is_saved'] = cursor.fetchone() is not None
            cursor.execute("SELECT 1 FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'complete'", (user_id, kata_id))
            kata_dict['is_completed'] = cursor.fetchone() is not None

        return kata_dict
    return None

@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    
    db = get_db()
    cursor = db.cursor()

    query = "SELECT k.*, u.display_name as author_display_name FROM katas k JOIN users u ON k.author_id = u.id"
    conditions = []
    params = []

    difficulty_filter = request.args.get('difficulty')
    if difficulty_filter:
        conditions.append("k.difficulty = ?")
        params.append(difficulty_filter)

    completion_time_filter = request.args.get('completion_time')
    if completion_time_filter:
        conditions.append("k.completion_time = ?")
        params.append(completion_time_filter)

    topic_filter = request.args.get('topic')
    if topic_filter:
        # Subquery to filter by topic
        conditions.append("k.id IN (SELECT kt.kata_id FROM kata_topics kt JOIN topics t ON kt.topic_id = t.id WHERE t.name = ?)")
        params.append(topic_filter)

    search_query = request.args.get('search')
    if search_query:
        # Use FTS5 for searching titles and content
        conditions.append("k.id IN (SELECT rowid FROM katas_fts WHERE katas_fts MATCH ?)")
        params.append(search_query + '*') # Add wildcard for prefix matching

    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    # Get total count for pagination
    count_query = query.replace("SELECT k.*, u.display_name as author_display_name", "SELECT COUNT(k.id)")
    cursor.execute(count_query, params)
    total_katas = cursor.fetchone()[0]

    query += " LIMIT ? OFFSET ?"
    params.extend([KATAS_PER_PAGE, (page - 1) * KATAS_PER_PAGE])

    cursor.execute(query, params)
    katas_data = cursor.fetchall()

    paginated_katas = []
    user = get_current_user()
    user_id = user['id'] if user else None

    for kata_row in katas_data:
        kata_dict = dict(kata_row)
        kata_dict['author_id'] = kata_row['author_display_name'] # Use display name
        # Fetch topics for each kata
        cursor.execute("SELECT t.name FROM topics t JOIN kata_topics kt ON t.id = kt.topic_id WHERE kt.kata_id = ?", (kata_row['id'],))
        kata_dict['topics'] = [row['name'] for row in cursor.fetchall()]

        if user_id:
            cursor.execute("SELECT 1 FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'upvote'", (user_id, kata_row['id']))
            kata_dict['is_upvoted'] = cursor.fetchone() is not None
            cursor.execute("SELECT 1 FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'save'", (user_id, kata_row['id']))
            kata_dict['is_saved'] = cursor.fetchone() is not None
            cursor.execute("SELECT 1 FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'complete'", (user_id, kata_row['id']))
            kata_dict['is_completed'] = cursor.fetchone() is not None

        paginated_katas.append(kata_dict)

    total_pages = (total_katas + KATAS_PER_PAGE - 1) // KATAS_PER_PAGE
    return render_template('index.html', 
                           katas=paginated_katas, 
                           user=user, 
                           page=page, 
                           total_pages=total_pages,
                           current_difficulty=difficulty_filter,
                           current_completion_time=completion_time_filter,
                           current_topic=topic_filter,
                           search_query=search_query)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        secret_username = request.form['secret_username']
        db = get_db()
        cursor = db.cursor()
        cursor.execute("SELECT * FROM users WHERE secret_username = ?", (secret_username,))
        user = cursor.fetchone()

        if user:
            session['username'] = secret_username
            return redirect(url_for('index'))
        else:
            # New user registration
            display_name = request.form['display_name']
            if display_name:
                cursor.execute("INSERT INTO users (secret_username, display_name) VALUES (?, ?)", (secret_username, display_name))
                db.commit()
                session['username'] = secret_username
                flash(f'Welcome! Your secret username is {secret_username}. Please save it for future logins.', 'success')
                return redirect(url_for('index'))
            else:
                flash('Please provide a display name for registration.', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

def validate_kata_data(kata_data):
    errors = []
    title = kata_data.get('title')
    content = kata_data.get('content')
    topics = kata_data.get('topics', [])
    difficulty = kata_data.get('difficulty')
    completion_time = kata_data.get('completion_time')

    if not title or not title.strip():
        errors.append('Title is required.')
    if not content or not content.strip():
        errors.append('Content is required.')
    if len(title) > 100:
        errors.append('Title cannot be longer than 100 characters.')
    if len(content) > 10000:
        errors.append('Content cannot be longer than 10000 characters.')
    if difficulty not in ALLOWED_DIFFICULTIES:
        errors.append('Invalid difficulty.')
    if completion_time not in ALLOWED_COMPLETION_TIMES:
        errors.append('Invalid completion time.')
    if len(topics) > 5:
        errors.append('You can only add up to 5 topics.')
    for topic in topics:
        if len(topic) > 20:
            errors.append('Each topic must be 20 characters or less.')
            break
    return errors

@app.route('/submit', methods=['GET', 'POST'])
def submit_kata():
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        topics_str = request.form['topics']
        topics = [t.strip() for t in topics_str.split(',') if t.strip()]
        difficulty = request.form['difficulty']
        completion_time = request.form['completion_time']

        kata_data = {
            'title': title,
            'content': content,
            'topics': topics,
            'difficulty': difficulty,
            'completion_time': completion_time
        }

        errors = validate_kata_data(kata_data)
        if errors:
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('submit_kata'))

        kata_id = str(uuid.uuid4())
        author_id = user['id']

        db = get_db()
        cursor = db.cursor()

        cursor.execute("INSERT INTO katas (id, title, content, author_id, difficulty, completion_time) VALUES (?, ?, ?, ?, ?, ?)",
                       (kata_id, title, content, author_id, difficulty, completion_time))
        
        # Insert topics and link to kata
        topics_text_for_fts = []
        for topic_name in topics:
            cursor.execute("INSERT OR IGNORE INTO topics (name) VALUES (?) ", (topic_name,))
            cursor.execute("SELECT id FROM topics WHERE name = ?", (topic_name,))
            topic_id = cursor.fetchone()[0]
            cursor.execute("INSERT INTO kata_topics (kata_id, topic_id) VALUES (?, ?)", (kata_id, topic_id))
            topics_text_for_fts.append(topic_name)
        
        # Insert into FTS table (removed rowid)
        cursor.execute("INSERT INTO katas_fts (title, content, topics_text) VALUES (?, ?, ?)",
                       (title, content, " ".join(topics_text_for_fts)))

        db.commit()
        flash('Kata submitted successfully!', 'success')
        return redirect(url_for('view_kata', kata_id=kata_id))
    return render_template('submit.html', user=user, allowed_completion_times=ALLOWED_COMPLETION_TIMES, allowed_difficulties=ALLOWED_DIFFICULTIES)

@app.route('/preview', methods=['POST'])
def preview():
    data = request.get_json()
    content = data.get('content', '')
    # Fix for empty LaTeX delimiters
    if re.search(r'\$\$\s*\$\$', content):
        return ""
    html_content = markdown2.markdown(content, extras=["fenced-code-blocks", "latex"])
    return html_content

@app.route('/kata/<kata_id>')
def view_kata(kata_id):
    user = get_current_user()
    user_id = user['id'] if user else None
    kata = get_kata_by_id(kata_id, user_id)
    if kata:
        # Fix for empty LaTeX delimiters
        if not re.search(r'\$\$\s*\$\$', kata['content']):
            kata['html_content'] = markdown2.markdown(kata['content'], extras=["fenced-code-blocks", "latex"])
        else:
            kata['html_content'] = markdown2.markdown(re.sub(r'\$\$\s*\$\$', '', kata['content']), extras=["fenced-code-blocks", "latex"])
        return render_template('view_kata.html', kata=kata, user=user)
    return 'Kata not found', 404

@app.route('/kata/<kata_id>/upvote', methods=['POST'])
def upvote_kata(kata_id):
    user = get_current_user()
    if not user:
        flash('Please log in to upvote katas.', 'error')
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    
    # Check if already upvoted
    cursor.execute("SELECT 1 FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'upvote'", (user['id'], kata_id))
    already_upvoted = cursor.fetchone()

    if already_upvoted:
        cursor.execute("DELETE FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'upvote'", (user['id'], kata_id))
        cursor.execute("UPDATE katas SET upvotes = upvotes - 1 WHERE id = ?", (kata_id,))
        flash('Upvote removed.', 'info')
    else:
        cursor.execute("INSERT INTO user_kata_actions (user_id, kata_id, action_type) VALUES (?, ?, ?)", (user['id'], kata_id, 'upvote'))
        cursor.execute("UPDATE katas SET upvotes = upvotes + 1 WHERE id = ?", (kata_id,))
        flash('Kata upvoted successfully!', 'success')
    db.commit()
    
    source = request.form.get('source')
    if source == 'index':
        query_params = {k: v for k, v in request.args.items() if k != 'page'}
        return redirect(url_for('index', page=request.args.get('page', 1, type=int), **query_params))
    elif source == 'saved':
        return redirect(url_for('saved_katas'))
    elif source == 'completed':
        return redirect(url_for('completed_katas'))
    return redirect(url_for('view_kata', kata_id=kata_id))

@app.route('/kata/<kata_id>/save', methods=['POST'])
def save_kata(kata_id):
    user = get_current_user()
    if not user:
        flash('Please log in to save katas.', 'error')
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    
    # Check if already saved
    cursor.execute("SELECT 1 FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'save'", (user['id'], kata_id))
    already_saved = cursor.fetchone()

    if already_saved:
        cursor.execute("DELETE FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'save'", (user['id'], kata_id))
        cursor.execute("UPDATE katas SET saves = saves - 1 WHERE id = ?", (kata_id,))
        flash('Kata unsaved.', 'info')
    else:
        cursor.execute("INSERT INTO user_kata_actions (user_id, kata_id, action_type) VALUES (?, ?, ?)", (user['id'], kata_id, 'save'))
        cursor.execute("UPDATE katas SET saves = saves + 1 WHERE id = ?", (kata_id,))
        flash('Kata saved successfully!', 'success')
    db.commit()

    source = request.form.get('source')
    if source == 'index':
        query_params = {k: v for k, v in request.args.items() if k != 'page'}
        return redirect(url_for('index', page=request.args.get('page', 1, type=int), **query_params))
    elif source == 'saved':
        return redirect(url_for('saved_katas'))
    elif source == 'completed':
        return redirect(url_for('completed_katas'))
    return redirect(url_for('view_kata', kata_id=kata_id))

@app.route('/kata/<kata_id>/complete', methods=['POST'])
def complete_kata(kata_id):
    user = get_current_user()
    if not user:
        flash('Please log in to mark katas as complete.', 'error')
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    
    # Check if already completed
    cursor.execute("SELECT 1 FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'complete'", (user['id'], kata_id))
    already_completed = cursor.fetchone()

    if already_completed:
        cursor.execute("DELETE FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'complete'", (user['id'], kata_id))
        cursor.execute("UPDATE katas SET completions = completions - 1 WHERE id = ?", (kata_id,))
        flash('Kata unmarked as complete.', 'info')
    else:
        cursor.execute("INSERT INTO user_kata_actions (user_id, kata_id, action_type) VALUES (?, ?, ?)", (user['id'], kata_id, 'complete'))
        cursor.execute("UPDATE katas SET completions = completions + 1 WHERE id = ?", (kata_id,))
        flash('Kata marked as complete!', 'success')
    db.commit()

    source = request.form.get('source')
    if source == 'index':
        query_params = {k: v for k, v in request.args.items() if k != 'page'}
        return redirect(url_for('index', page=request.args.get('page', 1, type=int), **query_params))
    elif source == 'saved':
        return redirect(url_for('saved_katas'))
    elif source == 'completed':
        return redirect(url_for('completed_katas'))
    return redirect(url_for('view_kata', kata_id=kata_id))

def get_katas_by_action(user_id, action_type):
    db = get_db()
    cursor = db.cursor()
    cursor.execute("SELECT k.*, u.display_name as author_display_name FROM katas k JOIN user_kata_actions uka ON k.id = uka.kata_id JOIN users u ON k.author_id = u.id WHERE uka.user_id = ? AND uka.action_type = ?", (user_id, action_type))
    katas_data = cursor.fetchall()

    katas_list = []
    for kata_row in katas_data:
        kata_dict = dict(kata_row)
        kata_dict['author_id'] = kata_row['author_display_name']
        cursor.execute("SELECT t.name FROM topics t JOIN kata_topics kt ON t.id = kt.topic_id WHERE kt.kata_id = ?", (kata_row['id'],))
        kata_dict['topics'] = [row['name'] for row in cursor.fetchall()]

        # Fetch user action status for saved katas
        cursor.execute("SELECT 1 FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'upvote'", (user_id, kata_row['id']))
        kata_dict['is_upvoted'] = cursor.fetchone() is not None
        cursor.execute("SELECT 1 FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'save'", (user_id, kata_row['id']))
        kata_dict['is_saved'] = cursor.fetchone() is not None
        cursor.execute("SELECT 1 FROM user_kata_actions WHERE user_id = ? AND kata_id = ? AND action_type = 'complete'", (user_id, kata_row['id']))
        kata_dict['is_completed'] = cursor.fetchone() is not None

        katas_list.append(kata_dict)
    return katas_list

@app.route('/saved_katas')
def saved_katas():
    user = get_current_user()
    if not user:
        flash('Please log in to view your saved katas.', 'error')
        return redirect(url_for('login'))

    saved_katas_list = get_katas_by_action(user['id'], 'save')
    return render_template('kata_list.html', katas=saved_katas_list, user=user, page_title="Saved Katas")

@app.route('/completed_katas')
def completed_katas():
    user = get_current_user()
    if not user:
        flash('Please log in to view your completed katas.', 'error')
        return redirect(url_for('login'))

    completed_katas_list = get_katas_by_action(user['id'], 'complete')
    return render_template('kata_list.html', katas=completed_katas_list, user=user, page_title="Completed Katas")

@app.route('/bulk_upload_katas', methods=['POST'])
def bulk_upload_katas():
    user = get_current_user()
    if not user:
        flash('Please log in to bulk upload katas.', 'error')
        return redirect(url_for('login'))

    db = get_db()
    cursor = db.cursor()
    uploaded_count = 0
    errors = []

    json_data_str = request.form.get('json_data')
    json_file = request.files.get('json_file')

    kata_data_list = []

    if json_data_str:
        try:
            kata_data_list.extend(json.loads(json_data_str))
        except json.JSONDecodeError as e:
            errors.append(f"Error parsing JSON data: {e}")

    if json_file and json_file.filename != '':
        try:
            file_content = json_file.read().decode('utf-8')
            kata_data_list.extend(json.loads(file_content))
        except json.JSONDecodeError as e:
            errors.append(f"Error parsing JSON file: {e}")
        except Exception as e:
            errors.append(f"Error reading JSON file: {e}")

    if not kata_data_list and not errors:
        flash('No JSON data or file provided for bulk upload.', 'info')
        return redirect(url_for('submit_kata'))

    for kata_data in kata_data_list:
        try:
            # Adapt to the expected structure for validate_kata_data
            topics_str = kata_data.get('topics', '')
            kata_data['topics'] = [t.strip() for t in topics_str.split(',') if t.strip()]

            validation_errors = validate_kata_data(kata_data)
            if validation_errors:
                for error in validation_errors:
                    errors.append(f"Error for kata '{kata_data.get('title', 'N/A')}': {error}")
                continue

            title = kata_data.get('title')
            content = kata_data.get('content')
            topics = kata_data.get('topics')
            difficulty = kata_data.get('difficulty')
            completion_time = kata_data.get('completion_time')

            kata_id = str(uuid.uuid4())
            author_id = user['id']

            cursor.execute("INSERT INTO katas (id, title, content, author_id, difficulty, completion_time) VALUES (?, ?, ?, ?, ?, ?)",
                           (kata_id, title, content, author_id, difficulty, completion_time))
            
            topics_text_for_fts = []
            for topic_name in topics:
                cursor.execute("INSERT OR IGNORE INTO topics (name) VALUES (?) ", (topic_name,))
                cursor.execute("SELECT id FROM topics WHERE name = ?", (topic_name,))
                topic_id = cursor.fetchone()[0]
                cursor.execute("INSERT INTO kata_topics (kata_id, topic_id) VALUES (?, ?)", (kata_id, topic_id))
                topics_text_for_fts.append(topic_name)
            
            cursor.execute("INSERT INTO katas_fts (title, content, topics_text) VALUES (?, ?, ?)",
                           (title, content, " ".join(topics_text_for_fts)))

            uploaded_count += 1
        except Exception as e:
            errors.append(f"Error processing kata {kata_data.get('title', 'N/A')}: {e}")
            db.rollback()
            continue
    
    db.commit()

    if uploaded_count > 0:
        flash(f'Successfully uploaded {uploaded_count} katas.', 'success')
    if errors:
        for error_msg in errors:
            flash(error_msg, 'error')

    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)