from flask import Flask, render_template, request, redirect, session, url_for, flash
import psycopg2
from collections import namedtuple
from werkzeug.exceptions import MethodNotAllowed

app = Flask(__name__)
app.secret_key = 'your_secret_key'

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
    app.permanent_session_lifetime = 120  # Session lifetime in seconds 

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
        
    particles_config = {
        "particles": {
            "number": {
                "value": 80,
                "density": {
                    "enable": True,
                    "value_area": 800
                }
            },
            "color": {
                "value": "#4caf50"
            },
            "shape": {
                "type": "star",
                "stroke": {
                    "width": 0.7,
                    "color": "#bbdebd"
                },
                "polygon": {
                    "nb_sides": 12
                },
                "image": {
                    "src": "img/github.svg",
                    "width": 100,
                    "height": 100
                }
            },
            "opacity": {
                "value": 1,
                "random": True,
                "anim": {
                    "enable": False,
                    "speed": 0.2,
                    "opacity_min": 0,
                    "sync": False
                }
            },
            "size": {
                "value": 2.8,
                "random": True,
                "anim": {
                    "enable": False,
                    "speed": 40,
                    "size_min": 0.1,
                    "sync": False
                }
            },
            "line_linked": {
                "enable": True,
                "distance": 200,
                "color": "#4caf50",
                "opacity": 0.4,
                "width": 1
            },
            "move": {
                "enable": True,
                "speed": 6,
                "direction": "none",
                "random": False,
                "straight": False,
                "out_mode": "out",
                "bounce": False,
                "attract": {
                    "enable": True,
                    "rotateX": 600,
                    "rotateY": 1200
                }
            }
        },
        "interactivity": {
            "detect_on": "canvas",
            "events": {
                "onhover": {
                    "enable": True,
                    "mode": "bubble"
                },
                "onclick": {
                    "enable": True,
                    "mode": "repulse"
                },
                "resize": True
            },
            "modes": {
                "grab": {
                    "distance": 400,
                    "line_linked": {
                        "opacity": 1
                    }
                },
                "bubble": {
                    "distance": 400,
                    "size": 40,
                    "duration": 2,
                    "opacity": 0.5,
                    "speed": 3
                },
                "repulse": {
                    "distance": 250,
                    "duration": 0.4
                },
                "push": {
                    "particles_nb": 4
                },
                "remove": {
                    "particles_nb": 2
                }
            }
        },
        "retina_detect": True
    }

    return render_template('login.html', particles_config=particles_config)
    #return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']

    # Check if the username is in the validator list
    if username in validator_usernames:
        
        if password == 'admin':
            session['username'] = username
            session['role'] = 'validator'
            return redirect('/validate')

    # Check if the username is in the questioner list
    elif username in questioner_usernames:

        if password == 'student':
            session['username'] = username
            session['role'] = 'questioner'
            return redirect('/submit_query')

    return 'Invalid username or password'
    # Invalid login - Render login page with error message
    # error_message = "Invalid username or password"
    # return redirect('/login', error = )

@app.route('/submit_query', methods=['GET', 'POST'])
@login_required
def submit_query():
    if request.method == 'GET' and session['role'] != 'questioner':
        return redirect(url_for('index'))

    if request.method == 'POST':
        if 'execute' in request.form:  # Execute the query
            query = request.form['query'].strip()
            if not query:
                flash('Query cannot be empty')
                return redirect(url_for('submit_query'))

            try:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    result = cursor.fetchall()  # Get the query result
                conn.commit()  # Commit the transaction if the query is successful
            except psycopg2.Error as e:
                conn.rollback()  # Rollback the transaction if there's an error
                flash(f'Error executing query: {e}')
                return redirect(url_for('submit_query'))

            return render_template('index.html', query=query, result=result, question=request.form['question'])

        elif 'submit' in request.form:  # Submit the query-question pair
            query = request.form['query'].strip()
            question = request.form['question'].strip()

            if not query:
                return 'Query cannot be empty', 400
            if not question:
                return 'Question cannot be empty', 400

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
            return 'Query-question pair submitted successfully'

    # Check if the route was accessed with pre-populated data
    query = request.args.get('query', '')
    question = request.args.get('question', '')
    remarks = request.args.get('remarks', '')

    return render_template('index.html', query=query, question=question, remarks=remarks)

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
    return render_template('logout.html')

if __name__ == '__main__':
    app.run(debug=True, port=5123) 