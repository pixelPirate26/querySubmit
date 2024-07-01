from flask import Flask, render_template, request, redirect, session, url_for, flash
from pymongo import MongoClient
from collections import namedtuple
from werkzeug.exceptions import MethodNotAllowed
from bson.json_util import dumps, loads
import json
import re  # Import regex module for validation

app = Flask(__name__)
app.secret_key = 'SpeakQL_Portal'

# MongoDB connection details
client = MongoClient("mongodb://localhost:27017/")
admin_db = client['admin_db']
final_data_db = client['final_data']  # New database for storing submitted data

QueryPair = namedtuple('QueryPair', ['id', 'query', 'question', 'username'])
pairs = []

# Sample user data structure
users = {
    'student1': {'password': 'student', 'role': 'questioner', 'assigned_db': 'admin', 'schema_links': 'https://example.com/schemas'},
    'student2': {'password': 'student', 'role': 'questioner', 'assigned_db': 'student2_db', 'schema_links': ''},
    # Add other users here
}

def login_required(func):
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('index'))
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

@app.before_request
def make_session_permanent():
    session.permanent = True
    app.permanent_session_lifetime = 180  # Session lifetime in seconds

@app.teardown_appcontext
def remove_session(exception=None):
    if session:
        session.clear()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        return redirect(url_for('index'))
    if 'username' in session:
        if session['role'] == 'questioner':
            return redirect('/submit_query')
        
    with open('static/particlesConfigLogin.json', 'r') as file:
        particles_config_login = json.load(file)

    return render_template('login.html', particles_config=particles_config_login)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    user = users.get(username)
    if user and user['password'] == password:
        session['username'] = username
        session['role'] = user['role']
        session['assigned_db'] = user.get('assigned_db')
        session['schema_links'] = user.get('schema_links')
        return redirect('/submit_query')
    else:
        flash('Invalid username or password', 'error')
        return redirect(url_for('index'))

@app.route('/submit_query', methods=['GET', 'POST'])
@login_required
def submit_query():
    with open('static/particlesConfigQuery.json', 'r') as file:
        particles_config_query = json.load(file)

    if request.method == 'GET' and session['role'] != 'questioner':
        return redirect(url_for('index'))

    assigned_db = client[session['assigned_db']]
    default_mongo_collections = [
    'system.indexes', 'system.users', 'system.version', 
    'system.profile', 'system.js', 'system.views',
    'local.oplog.rs', 'local.replset.minvalid',
    'config.system.sessions', 'config.transactions']

    collections = [coll for coll in assigned_db.list_collection_names() 
               if not coll.startswith('system.') and coll not in default_mongo_collections]
    db_schema_url = session['schema_links'].format(session['username'])  # Update with actual logic

    if request.method == 'POST':
        collection_name = request.form['collection'].strip()
        query = request.form['query'].strip()
        question = request.form['question'].strip()
        result_str = ''

        if not collection_name:
            flash('Collection name cannot be empty', 'error')
            return redirect(url_for('submit_query'))

        # Validate if the query is an aggregation command
        if not re.match(rf"^db\.{re.escape(collection_name)}\.aggregate\(.+\)$", query):
            flash(f'Invalid command. Please submit a MongoDB shell aggregate command such as db.{collection_name}.aggregate([...]).', 'error')
            return redirect(url_for('submit_query'))

        collection = assigned_db[collection_name]

        if 'execute' in request.form:
            if not query:
                flash('Query cannot be empty', 'error')
                return redirect(url_for('submit_query'))
            if not question:
                flash('Question cannot be empty', 'error')
                return redirect(url_for('submit_query'))

            try:
                # Extract the actual aggregation pipeline from the query string
                pipeline_str = re.search(r"\((.+)\)$", query).group(1)
                pipeline = loads(pipeline_str)
                result = collection.aggregate(pipeline)
                result_str = dumps(result, indent=4)
            except json.JSONDecodeError:
                flash('Invalid JSON format in the aggregation pipeline. Please ensure your query contains valid JSON.', 'error')
                return redirect(url_for('submit_query'))
            except Exception as e:
                flash(f'Error executing query: {e}', 'error')
                return redirect(url_for('submit_query'))

            return render_template('index.html', collections=collections, collection=collection_name, query=query, result=result_str, question=question, particles_config=particles_config_query, db_schema_url=db_schema_url)

        elif 'submit' in request.form:
            if not query:
                flash('Query cannot be empty', 'error')
                return redirect(url_for('submit_query'))
            if not question:
                flash('Question cannot be empty', 'error')
                return redirect(url_for('submit_query'))

            # Create 'training_data' collection if it doesn't exist
            if 'training_data' not in final_data_db.list_collection_names():
                final_data_db.create_collection('training_data')

            training_data = final_data_db['training_data']

            # Prepare the document to insert
            document = {
                'question': question,
                'query': query,
                'collection': collection_name,
                'username': session['username'],
                'db_name': session['assigned_db']
            }

            # Insert the document
            training_data.insert_one(document)

            flash('Query-question pair submitted and stored successfully!', 'success')

    collection = request.args.get('collection', '')
    query = request.args.get('query', '')
    question = request.args.get('question', '')
    remarks = request.args.get('remarks', '')

    return render_template('index.html', collections=collections, collection=collection, query=query, question=question, remarks=remarks, particles_config=particles_config_query, db_schema_url=db_schema_url)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5123)
