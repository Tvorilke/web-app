from flask import Flask, render_template, request, redirect, url_for, make_response, flash, send_file
import sqlite3
import random
from markup import sent_tokenize, markup
from exercise_predicate_rule import task_rule_gen
from exercise_predicate_passive import task_pssv_gen
from flask_login import LoginManager, login_required, UserMixin, current_user, login_user, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
import itertools
import datetime
import uuid
from itertools import groupby
from operator import itemgetter


app = Flask(__name__)
app.config['SECRET_KEY'] = 'Fiy67'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'log_in'


class User(UserMixin):
    def __init__(self, user):
        self.id = user[0]
        self.name = user[1]
        self.login = user[2]
        self.password = user[3]
        self.email = user[4]
        self.type = user[5]


@app.route('/log-in')
def log_in():
    return render_template('index.html',
                           auth=current_user.is_authenticated,
                           page_template='log_in.html')


@app.route('/log-in', methods=['GET', 'POST'])
def log_in_form():
    sqlite_connection = db_connect()
    cursor = sqlite_connection.cursor()
    email = request.form.get('email')
    user_password = request.form.get('password')
    try:
        db_password = cursor.execute("SELECT password from users WHERE email = (?);", [email]).fetchone()[0]
    except TypeError:
        flash('Введенный email неверен.')
        sqlite_connection.close()
        return redirect(url_for('log_in'))
    if check_password_hash(db_password, user_password):
        user_id = cursor.execute("SELECT id from users WHERE email = (?);", [email]).fetchone()[0]
        user = load_user(user_id)
        login_user(user)
        sqlite_connection.close()
        return redirect(url_for('profile'))
    else:
        flash('Введенный пароль или email неверен.')
        sqlite_connection.close()
        return redirect(url_for('log_in'))


@app.route('/sign-up')
def sign_up():
    return render_template('index.html',
                           auth=current_user.is_authenticated,
                           page_template='sign_up.html')


@app.route('/sign-up', methods=['POST'])
def sign_up_form():
    if request.method == 'POST':
        sqlite_connection = db_connect()
        cursor = sqlite_connection.cursor()
        name = request.form.get('name')
        login = request.form.get('login')
        password = request.form.get('password')
        password = generate_password_hash(password, method='sha256')
        email = request.form.get('email')
        u_type = request.form.get('type')
        if cursor.execute("SELECT * from users WHERE email = (?);", [email]).fetchall():
            flash('Такой email уже зарегистрирован. <a href="/log-in">Авторизируйтесь.</a>')
            return redirect(url_for('sign_up'))
        cursor.execute('INSERT INTO users (name, login, password, email, type) VALUES (?, ?, ?, ?, ?)',
                       (name, login, password, email, u_type))
        sqlite_connection.commit()
        flash('Вы успешно зарегистрированы.')
        user_id = cursor.execute("SELECT id from users WHERE email = (?);", [email]).fetchone()[0]
        user = load_user(user_id)
        login_user(user)
        sqlite_connection.close()
        return redirect(url_for('profile'))


@app.route('/log-out')
def log_out():
    logout_user()
    return render_template('index.html',
                           auth=current_user.is_authenticated,
                           page_template='body_index.html')


@login_manager.user_loader
def load_user(user_id):
    sqlite_connection = db_connect()
    cursor = sqlite_connection.cursor()
    user = cursor.execute("SELECT * FROM users where id = (?)", [user_id]).fetchone()
    sqlite_connection.close()
    if user:
        return User(user)
    else:
        return None


@app.route('/')
@app.route('/index')
def index():
    return render_template('index.html',
                           auth=current_user.is_authenticated,
                           page_template='body_index.html')


@app.route('/help')
def help_page():
    return render_template('index.html',
                           auth=current_user.is_authenticated,
                           page_template='body_help.html')


@app.route('/generation', methods=['get', 'post'])
def generation():
    if request.method == 'POST':
        task_type = request.form.get('task_type')
        sqlite_connection = db_connect()
        cursor = sqlite_connection.cursor()
        #subjects = cursor.execute("SELECT DISTINCT text_theme FROM exercises").fetchall()
        subjects = {"('Economy',)": 'Экономика и право', "('IT',)": 'Информационные технологии',
                    "('Law',)": 'Юридическая наука и практика'}
        sqlite_connection.close()
        reponse = make_response(render_template('index.html',
                                                auth=current_user.is_authenticated,
                                                task_type=task_type,
                                                subjects=subjects.items(),
                                                page_template='body_generation.html'))
        reponse.set_cookie('task_type', task_type)
        return reponse
    elif request.method == 'GET':
        task_type = request.cookies.get('task_type')
        reponse = make_response(render_template('index.html',
                                                auth=current_user.is_authenticated,
                                                task_type=task_type,
                                                page_template='body_generation.html'))
        return reponse


@app.route('/task', methods=['get', 'post'])
def exercise():
    task_title = {'rule': 'Глагольное управление', 'pssv': 'Сказуемое в пассивной форме'}
    task_discr = {'rule': 'Заполните пропуски словами в верной форме, ориентируясь на контекст. Каждый пропуск '
                          'соответсвует одному слову. Подлежащее в '
                          'предложении выделено <b>жирным</b> шрифтом.<br>Если упражнение '
                          'содержит ошибку, поставьте галочку в соответсвующем поле. При необходимости оставьте '
                          'комментарий. Это упражнение не будет учитываться при оценке выполнения теста. Так вы '
                          'поможете улучшить работу приложения.',
                  'pssv': 'Поставьте глагол в форму пассивного залога в соответсвии с контекстом. Подлежащее в '
                          'предложении выделено <b>жирным</b> шрифтом.<br>Если упражнение '
                          'содержит ошибку, поставьте галочку в соответсвующем поле. При необходимости оставьте '
                          'комментарий. Это упражнение не будет учитываться при оценке выполнения теста.Так вы '
                          'поможете улучшить работу приложения.'}
    if request.method == 'POST':
        text_file = ''
        subject = ''
        text_source = request.form.get('text-source')
        if text_source == 'file':
            text_file = request.form.get('text-file')
        exer_amount = request.form.get('amount')
        hint = request.form.get('hint')
        task_type = request.cookies.get('task_type')
        if text_source != 'file':
            subject = (request.form.get('subject')).split("'")[1]
        data = exer_generation(text_file, exer_amount, task_type, subject)
        if not data:
            flash("Не удалось сгенерировать задания из введенного текста. Попробуйте ввести другой!")
            return redirect(url_for('generation'))
        else:
            reponse = make_response(render_template('index.html',
                                                    auth=current_user.is_authenticated,
                                                    task_title=task_title[task_type],
                                                    task_discr=task_discr[task_type],
                                                    exer_amount=exer_amount,
                                                    hint=hint,
                                                    exercise=data,
                                                    task_type=task_type,
                                                    page_template='body_task.html'))
            if text_source == 'corpus':
                reponse.set_cookie('exer_id', ' '.join([str(row[0]) for row in data]))
            elif text_source == "file":
                reponse.set_cookie('tasks', '; '.join([rec[2] for rec in data]))
                reponse.set_cookie('words_to_mod', '; '.join([rec[3] for rec in data]))
                reponse.set_cookie('hints', '; '.join([rec[5] for rec in data]))
                reponse.set_cookie('answers', '; '.join([rec[4] for rec in data]))
            reponse.set_cookie('exer_amount', exer_amount)
            reponse.set_cookie('text_source', text_source)
            reponse.set_cookie('hint', hint)
            return reponse
    elif request.method == 'GET':
        records = []
        sqlite_connection = db_connect()
        cursor = sqlite_connection.cursor()
        exer_amount = request.cookies.get('exer_amount')
        hint = request.cookies.get('hint')
        exer_id = request.cookies.get('exer_id').split(' ')
        text_source = request.cookies.get('text_source')
        task_type = request.cookies.get('task_type')
        if text_source == 'corpus':
            for _ in exer_id:
                records.append(cursor.execute("SELECT * from exercises where id = {}".format(int(_))).fetchall()[0])
        elif text_source == 'file':
            tasks = request.cookies.get('tasks').split('; ')
            words_to_mod = request.cookies.get('words_to_mod').split('; ')
            hints = request.cookies.get('hints').split('; ')
            answers = request.cookies.get('answers').split('; ')
            records = [(0, task_type, task, words, answer, hint, 0) for (task, words, answer, hint) in
                       itertools.zip_longest(tasks, words_to_mod, answers, hints)]
        reponse = make_response(render_template('index.html',
                                                auth=current_user.is_authenticated,
                                                task_title=task_title[task_type],
                                                task_discr=task_discr[task_type],
                                                exer_amount=exer_amount,
                                                hint=hint,
                                                exercise=records,
                                                task_type=task_type,
                                                page_template='body_task.html'))
        sqlite_connection.close()
        return reponse


def add_to_db(records, marks, user_answers, errors, comments):
    user_id = current_user.id
    date = datetime.datetime.now()
    sqlite_connection = db_connect()
    cursor = sqlite_connection.cursor()
    test_id = str(uuid.uuid4())
    for (rec, mark, u_answ, err, comm) in itertools.zip_longest(records, marks, user_answers, errors, comments):
        cursor.execute('INSERT INTO solved_exercises (user_id, test_id, exer_id, mark, user_answer, date, error, '
                       'comment) VALUES (?, ?, ?, ?, ?, ?, ?, ?);',
                       (user_id, test_id, rec[0], mark, u_answ, date, err, comm))
    sqlite_connection.commit()
    sqlite_connection.close()


def db_connect():
    sqlite_connection = sqlite3.connect('web_app.db')
    return sqlite_connection


def exer_generation(text_file, exer_amount, task_type, subject):
    tasks_functions = {'rule': task_rule_gen, 'pssv': task_pssv_gen}
    exercises = []
    data = []
    sqlite_connection = db_connect()
    cursor = sqlite_connection.cursor()
    if current_user.is_authenticated:
        user_id = current_user.id
        used_exers = [rec[3] for rec in
                      cursor.execute("SELECT * FROM solved_exercises WHERE user_id = (?)", [user_id]).fetchall()]
    else:
        used_exers = []
    if not text_file:
        if subject == 'all':
            records = cursor.execute("SELECT * FROM exercises WHERE type = (?);", [task_type]).fetchall()
        else:
            records = cursor.execute("SELECT * FROM exercises WHERE type = (?) and text_theme = (?);", [task_type, subject]).fetchall()
        records = [rec for rec in records if rec[0] not in used_exers]
        data = random.sample(records, int(exer_amount))
    if text_file:
        sentences = sent_tokenize(text_file)
        for sent in sentences:
            exercises.append((sent, markup(sent), sentences.index(sent)))
        if len(exercises) >= int(exer_amount):
            for task in random.sample(exercises, int(exer_amount)):
                t = tasks_functions[task_type](task[0], task[1], task[2])
                if t:
                    t = list(t)
                    t.insert(0, 0)
                    t = tuple(t)
                    data.append(t)
        else:
            for task in exercises:
                t = tasks_functions[task_type](task[0], task[1], task[2])
                if t:
                    t = list(t)
                    t.insert(0, 0)
                    t = tuple(t)
                    data.append(t)
        if len(data) < int(exer_amount):
            flash("Количество сгенерированных упражнений меньше указанного, "
                  "так как во введенном тексте было недостаточно предложений.")
    sqlite_connection.close()
    return data


@app.route('/answers', methods=['post'])
def check_exer():
    comments = []
    records = []
    user_answers = []
    answers = []
    if request.method == 'POST':
        correct_answer = 0
        incorrect_answer = 0
        sqlite_connection = db_connect()
        cursor = sqlite_connection.cursor()
        task_type = request.cookies.get('task_type')
        text_source = request.cookies.get('text_source')
        if text_source == "corpus":
            exer_id = request.cookies.get('exer_id').split(' ')
            for _ in exer_id:
                records.append(cursor.execute("SELECT * from exercises where id = (?)", [int(_)]).fetchall()[0])
                answers.append(cursor.execute("SELECT * from exercises where id = (?)", [int(_)]).fetchall()[0][4])
        elif text_source == "file":
            tasks = request.cookies.get('tasks').split('; ')
            words_to_mod = request.cookies.get('words_to_mod').split('; ')
            hints = request.cookies.get('hints').split('; ')
            answers = request.cookies.get('answers').split('; ')
            records = [(0, task_type, task, words, answer, hint, 0) for (task, words, answer, hint) in
                       itertools.zip_longest(tasks, words_to_mod, answers, hints)]
        marks = [0] * len(answers)
        errors = [0] * len(answers)
        for answer in answers:
            ind = answers.index(answer)
            user_answer = request.form.get('user_answer' + '_' + str(ind + 1))
            user_answers.append(user_answer)
            comments.append(request.form.get('comment' + '_' + str(ind + 1)))
            if request.form.get('error' + '_' + str(ind + 1)):
                marks[ind] = -1
                errors[ind] = 1
            if user_answer.lower() == answers[ind].lower():
                correct_answer += 1
                marks[ind] = 1
            elif not request.form.get('error' + '_' + str(ind + 1)) and user_answer.lower() != answers[ind].lower():
                incorrect_answer += 1
                marks[ind] = 0
                errors[ind] = 0
        if current_user.is_authenticated and text_source == 'corpus':
            add_to_db(records, marks, user_answers, errors, comments)
        try:
            percent = correct_answer / (correct_answer + incorrect_answer) * 100
        except ZeroDivisionError:
            percent = 0
        sqlite_connection.close()
        return render_template('index.html',
                               auth=current_user.is_authenticated,
                               marks=marks,
                               percent=percent,
                               records=records,
                               user_answers=user_answers,
                               page_template='body_answers.html')


@app.route('/profile')
@login_required
def profile():
    sqlite_connection = db_connect()
    cursor = sqlite_connection.cursor()
    user_id = current_user.id
    user_marks = [rec[4] for rec in
                  cursor.execute("SELECT * FROM solved_exercises where user_id = (?)", [user_id]).fetchall()]
    solved_exers = [(rec) for rec in cursor.execute("SELECT exer_id, user_answer, date, mark, exer_text, answer, "
                                                    "test_id FROM solved_exercises INNER JOIN exercises on "
                                                    "solved_exercises.exer_id = exercises.id WHERE user_id = (?) ",
                                                    [user_id]).fetchall()]
    sqlite_connection.close()
    solved_exers.sort(key=itemgetter(6))
    solved_exers = groupby(solved_exers, itemgetter(6))
    tests = [[item for item in data] for (key, data) in solved_exers]
    tests.sort(key=lambda x: x[0][2])
    for test in tests:
        total_mark = round((sum([item[3] for item in test if item[3] != -1]) / len(test) * 100), 2)
        test.append(total_mark)
    correct = user_marks.count(1)
    incorrect = user_marks.count(0)
    mark_sum = correct + incorrect
    if not user_marks:
        return render_template('index.html',
                               auth=current_user.is_authenticated,
                               user=current_user,
                               page_template='body_profile_new.html')
    else:
        return render_template('index.html',
                               auth=current_user.is_authenticated,
                               correct=correct,
                               incorrect=incorrect,
                               mark_sum=mark_sum,
                               user=current_user,
                               solved_exers=tests,
                               page_template='body_profile.html')


"""@app.route('/task_file')
def task_file():
    return send_file('/Users/anastasiiaprisiazniuk/Downloads/task.pdf')"""


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5000, debug=True)
