from flask import Flask, render_template, request, redirect, session, url_for, flash
import psycopg2
from collections import namedtuple
from werkzeug.exceptions import MethodNotAllowed
import json

app = Flask(__name__)
app.secret_key = 'SpeakQL_Portal'

# PostgreSQL connection details
conn = psycopg2.connect(
    host="localhost",
    database="test",
    user="test",
    password="test",
    port=5432 
)

QueryPair = namedtuple('QueryPair', ['id', 'query', 'question', 'username'])
pairs = []  # submitted query-question pairs

validator_usernames = ['admin1', 'admin2', 'admin3', 'admin4', 'admin5', 'admin6']
questioner_usernames = ['student1', 'student2', 'student3', 'student4', 'student5', 'student6', 'student7', 'student8',
                        'student9', 'student10', 'student11', 'student12', 'student13', 'student14']

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
        elif session['role'] == 'validator':
            return redirect('/validate')
        
    with open('static/particlesConfigLogin.json', 'r') as file:
        particles_config_login = json.load(file)

    return render_template('login.html', particles_config = particles_config_login)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    if username in validator_usernames and password == 'admin':
        session['username'] = username
        session['role'] = 'validator'
        return redirect('/validate')
    elif username in questioner_usernames and password == 'student':
        session['username'] = username
        session['role'] = 'questioner'
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

    if request.method == 'POST':
        if 'execute' in request.form:
            query = request.form['query'].strip()
            question = request.form['question'].strip()
            if not query:
                flash('Query cannot be empty', 'error')
                return redirect(url_for('submit_query'))
            if not question:
                flash('Question cannot be empty', 'error')
                return redirect(url_for('submit_query'))
            try:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    result = cursor.fetchall()
                    conn.commit()
                    column_names = [desc[0] for desc in cursor.description]  # Get column names
            except psycopg2.Error as e:
                conn.rollback()
                flash(f'Error executing query: {e}')
                return redirect(url_for('submit_query'))

            if result:
                result_str = '<table>\n'
                result_str += '  <tr>\n'
                # Get column names from cursor.description
                column_names = [desc[0] for desc in cursor.description]
                for col_name in column_names:
                    result_str += f'        <th>{col_name}</th>\n'
                result_str += '  </tr>\n'

                # Loop through each row and display data in table cells
                for row in result:
                    result_str += '  <tr>\n'
                    for value in row:
                        result_str += f'    <td>{value}</td>\n'
                    result_str += '  </tr>\n'

                result_str += '</table>\n'
            else:
                '''result_str = '<table>\n'
                result_str += '  <tr>\n'
                for col_name in column_names:
                    result_str += f'    <th>{col_name}</th>\n'
                result_str += '  </tr>\n'
                result_str += '</table>\n'''
                result_str = '<p>No results found.</p>'

            return render_template('index.html', query=query, result=result_str, question=request.form['question'],particles_config=particles_config_query)

        elif 'submit' in request.form:  # Submit the query-question pair
            query = request.form['query'].strip()
            question = request.form['question'].strip()

            if not query:
                flash('Query cannot be empty', 'error')
                return redirect(url_for('submit_query'))
            if not question:
                flash('Question cannot be empty', 'error')
                return redirect(url_for('submit_query'))

            try:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    if cursor.rowcount == 0:
                        raise psycopg2.Error("No rows affected")
                conn.commit()  
            except psycopg2.Error as e:
                conn.rollback()  
                flash(f'Error executing query: {e}')
                return redirect(url_for('submit_query'))

            pair_id = len(pairs) + 1
            pairs.append(QueryPair(pair_id, query, question, session['username']))
            flash('Query-question pair submitted successfully!', 'success')


    # Check if the route was accessed with pre-populated data
    query = request.args.get('query', '')
    question = request.args.get('question', '')
    remarks = request.args.get('remarks', '')

    return render_template('index.html', query=query, question=question, remarks=remarks, particles_config=particles_config_query )

@app.route('/validate', methods=['GET', 'POST'])
@login_required
def validate():
    if request.method == 'GET' and session['role'] != 'validator':
        return redirect(url_for('index'))

    if request.method == 'POST':
        pair_id = int(request.form['pair_id'])
        is_valid = request.form.get('is_valid')
        remarks = request.form.get('remarks')

        # Get the query and question from the pair
        pair = next((p for p in pairs if p.id == pair_id), None)
        if pair:
            if is_valid == 'false':  # Invalid query
                # Redirect the questioner to the submit_query route with the invalid query and question
                questioner_username = pair.username
                return redirect(url_for('submit_query', query=pair.query, question=pair.question, remarks=remarks))

        # ToDO Implement validation logic 
        
        return 'Validation submitted successfully'

    return render_template('validate.html', pairs=pairs)

@app.errorhandler(MethodNotAllowed)
def method_not_allowed(e):
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, port=5123)
