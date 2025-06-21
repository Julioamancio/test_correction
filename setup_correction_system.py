import os

# ==== ARQUIVOS PRINCIPAIS ====
files = {
    ".env.example": """SECRET_KEY=uma-chave-muito-secreta
DATABASE_URL=sqlite:///db.sqlite3
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USERNAME=SEU_EMAIL@gmail.com
MAIL_PASSWORD=SENHA_DO_EMAIL
""",
    "requirements.txt": """Flask==3.0.2
Flask-Login==0.6.3
Flask-Mail==0.9.1
Flask-Migrate==4.0.5
Flask-SQLAlchemy==3.1.1
bcrypt==4.1.2
python-dotenv==1.0.1
transformers==4.41.2
torch==2.3.0
scikit-learn==1.5.0
gunicorn==22.0.0
""",
    "app.py": """from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)
""",
    "manage.py": """from flask_migrate import Migrate
from app import create_app, db

app = create_app()
migrate = Migrate(app, db)

if __name__ == "__main__":
    app.run(debug=True)
""",
    "app/__init__.py": """from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from dotenv import load_dotenv
import os

db = SQLAlchemy()
login_manager = LoginManager()
mail = Mail()
migrate = Migrate()

def create_app():
    load_dotenv()
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "changeme")
    app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv("DATABASE_URL", "sqlite:///db.sqlite3")
    app.config['MAIL_SERVER'] = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    app.config['MAIL_PORT'] = int(os.getenv("MAIL_PORT", 587))
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = os.getenv("MAIL_USERNAME")
    app.config['MAIL_PASSWORD'] = os.getenv("MAIL_PASSWORD")

    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)

    from .routes import main
    app.register_blueprint(main)

    return app
""",
    "app/models.py": """from . import db
from flask_login import UserMixin
from datetime import datetime
import bcrypt

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), unique=True)
    email = db.Column(db.String(150), unique=True)
    password_hash = db.Column(db.String(128))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(password.encode('utf-8'), self.password_hash.encode('utf-8'))

class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(20))  # 'objetiva', 'discursiva', 'redacao'
    statement = db.Column(db.Text)
    options = db.Column(db.Text)     # JSON string for options (objetiva)
    answer = db.Column(db.Text)      # Gabarito
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    answer_text = db.Column(db.Text)
    score = db.Column(db.Float)
    feedback = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
""",
    "app/routes.py": """from flask import Blueprint, render_template, redirect, url_for, request, flash, session
from flask_login import login_user, logout_user, current_user, login_required
from .models import db, User, Question, Answer
from .ml import correct_discursive, correct_objective
from . import login_manager, mail
from flask_mail import Message
import json

main = Blueprint('main', __name__)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        if User.query.filter((User.username==username)|(User.email==email)).first():
            flash('Usuário ou email já cadastrado', 'danger')
            return render_template('register.html')
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        flash('Cadastro realizado! Faça login.', 'success')
        return redirect(url_for('main.login'))
    return render_template('register.html')

@main.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form['email']).first()
        if user and user.check_password(request.form['password']):
            login_user(user)
            return redirect(url_for('main.dashboard'))
        flash('Credenciais inválidas', 'danger')
    return render_template('login.html')

@main.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('main.index'))

@main.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            token = f"{user.id}-{user.username}"
            msg = Message('Recuperação de Senha', recipients=[user.email])
            msg.body = f"Use o link para redefinir sua senha: {url_for('main.reset', token=token, _external=True)}"
            mail.send(msg)
            flash('E-mail de recuperação enviado!', 'info')
        else:
            flash('E-mail não encontrado.', 'danger')
    return render_template('forgot.html')

@main.route('/reset/<token>', methods=['GET', 'POST'])
def reset(token):
    user_id = int(token.split('-')[0])
    user = User.query.get(user_id)
    if not user:
        flash('Token inválido!', 'danger')
        return redirect(url_for('main.login'))
    if request.method == 'POST':
        password = request.form['password']
        user.set_password(password)
        db.session.commit()
        flash('Senha redefinida! Faça login.', 'success')
        return redirect(url_for('main.login'))
    return render_template('reset.html')

@main.route('/dashboard')
@login_required
def dashboard():
    questions = Question.query.filter_by(created_by=current_user.id).all()
    return render_template('dashboard.html', questions=questions)

@main.route('/question/new', methods=['GET', 'POST'])
@login_required
def new_question():
    if request.method == 'POST':
        type_ = request.form['type']
        statement = request.form['statement']
        options = json.dumps(request.form.getlist('options')) if type_ == 'objetiva' else None
        answer = request.form['answer']
        q = Question(type=type_, statement=statement, options=options, answer=answer, created_by=current_user.id)
        db.session.add(q)
        db.session.commit()
        flash('Questão adicionada!', 'success')
        return redirect(url_for('main.dashboard'))
    return render_template('new_question.html')

@main.route('/question/<int:qid>/answer', methods=['GET', 'POST'])
@login_required
def answer_question(qid):
    question = Question.query.get_or_404(qid)
    if request.method == 'POST':
        answer_text = request.form['answer']
        if question.type == 'objetiva':
            score, feedback = correct_objective(question, answer_text)
        else:
            score, feedback = correct_discursive(question, answer_text)
        ans = Answer(question_id=qid, user_id=current_user.id, answer_text=answer_text, score=score, feedback=feedback)
        db.session.add(ans)
        db.session.commit()
        flash('Resposta enviada! Veja a correção abaixo.', 'info')
        return render_template('answer_result.html', question=question, score=score, feedback=feedback)
    return render_template('answer_question.html', question=question)
""",
    "app/ml.py": """import json

def correct_objective(question, student_answer):
    options = json.loads(question.options)
    gabarito = question.answer
    if student_answer.strip().lower() == gabarito.strip().lower():
        return 1.0, "Correto!"
    return 0.0, f"Incorreto. Resposta correta: {gabarito}"

def correct_discursive(question, student_answer):
    try:
        from transformers import pipeline
        scorer = pipeline("text-classification", model="cross-encoder/nli-distilroberta-base")
        result = scorer(f"{student_answer} [SEP] {question.answer}")
        score = float(result[0]['score'])
        feedback = "Sua resposta está próxima da ideal." if score > 0.7 else "Sua resposta pode ser melhorada."
        return score, feedback
    except Exception:
        return 0.5, "Correção automática indisponível, avalie manualmente."
""",
}

# ==== TEMPLATES (HTML) ====
templates = {
    "base.html": """<!DOCTYPE html>
<html lang="pt">
<head>
    <meta charset="UTF-8">
    <title>{% block title %}Correção Provas{% endblock %}</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css">
    <link rel="icon" href="{{ url_for('static', filename='favicon.ico') }}">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <style>
        body { background: #f8f9fa; }
        .card { border-radius: 1rem; }
        .navbar { border-radius: 0 0 1rem 1rem; }
    </style>
    {% block head %}{% endblock %}
</head>
<body>
<nav class="navbar navbar-expand-lg navbar-dark bg-primary mb-4">
  <div class="container">
    <a class="navbar-brand" href="{{ url_for('main.index') }}">CorreçãoPro</a>
    <div class="collapse navbar-collapse">
      <ul class="navbar-nav ms-auto">
        {% if current_user.is_authenticated %}
        <li class="nav-item"><a class="nav-link" href="{{ url_for('main.dashboard') }}">Dashboard</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('main.logout') }}">Sair</a></li>
        {% else %}
        <li class="nav-item"><a class="nav-link" href="{{ url_for('main.login') }}">Login</a></li>
        <li class="nav-item"><a class="nav-link" href="{{ url_for('main.register') }}">Cadastro</a></li>
        {% endif %}
      </ul>
    </div>
  </div>
</nav>
<main class="container">
    {% with messages = get_flashed_messages(with_categories=true) %}
      {% if messages %}
        {% for category, message in messages %}
          <div class="alert alert-{{ category }} alert-dismissible fade show" role="alert">
            {{ message }}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
          </div>
        {% endfor %}
      {% endif %}
    {% endwith %}
    {% block content %}{% endblock %}
</main>
</body>
</html>
""",
    "index.html": """{% extends 'base.html' %}
{% block title %}Bem-vindo!{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-6">
        <div class="card shadow p-4 text-center">
            <h1 class="mb-3">Correção Automática de Provas</h1>
            <p>Solução profissional para correção de questões objetivas, discursivas e redações!</p>
            <a class="btn btn-primary btn-lg" href="{{ url_for('main.register') }}">Comece Agora</a>
        </div>
    </div>
</div>
{% endblock %}
""",
    "register.html": """{% extends 'base.html' %}
{% block title %}Cadastro{% endblock %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-5">
    <div class="card shadow p-4">
      <h2>Cadastro</h2>
      <form method="post">
        <div class="mb-3">
          <label>Nome de usuário</label>
          <input type="text" class="form-control" name="username" required>
        </div>
        <div class="mb-3">
          <label>Email</label>
          <input type="email" class="form-control" name="email" required>
        </div>
        <div class="mb-3">
          <label>Senha</label>
          <input type="password" class="form-control" name="password" required>
        </div>
        <button class="btn btn-success" type="submit">Cadastrar</button>
      </form>
      <hr>
      <a href="{{ url_for('main.login') }}">Já tem uma conta? Entrar</a>
    </div>
  </div>
</div>
{% endblock %}
""",
    "login.html": """{% extends 'base.html' %}
{% block title %}Login{% endblock %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-5">
    <div class="card shadow p-4">
      <h2>Login</h2>
      <form method="post">
        <div class="mb-3">
          <label>Email</label>
          <input type="email" class="form-control" name="email" required>
        </div>
        <div class="mb-3">
          <label>Senha</label>
          <input type="password" class="form-control" name="password" required>
        </div>
        <button class="btn btn-primary" type="submit">Entrar</button>
      </form>
      <hr>
      <a href="{{ url_for('main.forgot') }}">Esqueci minha senha</a>
    </div>
  </div>
</div>
{% endblock %}
""",
    "forgot.html": """{% extends 'base.html' %}
{% block title %}Recuperar Senha{% endblock %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-5">
    <div class="card shadow p-4">
      <h2>Recuperar Senha</h2>
      <form method="post">
        <div class="mb-3">
          <label>Email</label>
          <input type="email" class="form-control" name="email" required>
        </div>
        <button class="btn btn-warning" type="submit">Enviar link de recuperação</button>
      </form>
      <hr>
      <a href="{{ url_for('main.login') }}">Voltar ao login</a>
    </div>
  </div>
</div>
{% endblock %}
""",
    "reset.html": """{% extends 'base.html' %}
{% block title %}Redefinir Senha{% endblock %}
{% block content %}
<div class="row justify-content-center">
  <div class="col-md-5">
    <div class="card shadow p-4">
      <h2>Redefinir Senha</h2>
      <form method="post">
        <div class="mb-3">
          <label>Nova Senha</label>
          <input type="password" class="form-control" name="password" required>
        </div>
        <button class="btn btn-success" type="submit">Salvar nova senha</button>
      </form>
    </div>
  </div>
</div>
{% endblock %}
""",
    "dashboard.html": """{% extends 'base.html' %}
{% block title %}Dashboard{% endblock %}
{% block content %}
<div class="mb-4 text-center">
    <a class="btn btn-primary" href="{{ url_for('main.new_question') }}"><span class="bi bi-plus-circle"></span> Nova Questão</a>
</div>
<div class="row">
    {% for q in questions %}
    <div class="col-md-6 mb-3">
        <div class="card shadow-sm p-3">
            <h5>{{ q.statement|truncate(60) }}</h5>
            <span class="badge bg-secondary">{{ q.type }}</span>
            <a href="{{ url_for('main.answer_question', qid=q.id) }}" class="btn btn-outline-success mt-2">Responder</a>
        </div>
    </div>
    {% endfor %}
    {% if not questions %}
    <div class="col-12 text-center text-muted">Nenhuma questão cadastrada.</div>
    {% endif %}
</div>
{% endblock %}
""",
    "new_question.html": """{% extends 'base.html' %}
{% block title %}Nova Questão{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card shadow p-4">
            <h2>Nova Questão</h2>
            <form method="post">
                <div class="mb-3">
                    <label>Tipo de questão</label>
                    <select name="type" id="type" class="form-select" required onchange="toggleOptions()">
                        <option value="objetiva">Múltipla Escolha</option>
                        <option value="discursiva">Discursiva</option>
                        <option value="redacao">Redação</option>
                    </select>
                </div>
                <div class="mb-3">
                    <label>Enunciado</label>
                    <textarea class="form-control" name="statement" required rows="3"></textarea>
                </div>
                <div class="mb-3" id="options-div">
                    <label>Alternativas (um por linha)</label>
                    <textarea class="form-control" name="options" rows="4"></textarea>
                </div>
                <div class="mb-3">
                    <label>Resposta Correta (ou gabarito)</label>
                    <input type="text" name="answer" class="form-control" required>
                </div>
                <button class="btn btn-success" type="submit">Salvar</button>
            </form>
        </div>
    </div>
</div>
<script>
function toggleOptions() {
    const select = document.getElementById('type');
    document.getElementById('options-div').style.display = (select.value === 'objetiva') ? 'block' : 'none';
}
toggleOptions();
</script>
{% endblock %}
""",
    "answer_question.html": """{% extends 'base.html' %}
{% block title %}Responder Questão{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card shadow p-4">
            <h2>Responder</h2>
            <div class="mb-3">
                <strong>Enunciado:</strong>
                <p>{{ question.statement }}</p>
                {% if question.type == "objetiva" %}
                    <ul>
                    {% for opt in question.options|fromjson %}
                        <li>{{ opt }}</li>
                    {% endfor %}
                    </ul>
                {% endif %}
            </div>
            <form method="post">
                <div class="mb-3">
                    <label>Sua resposta</label>
                    <textarea class="form-control" name="answer" required rows="3"></textarea>
                </div>
                <button class="btn btn-success" type="submit">Enviar</button>
            </form>
        </div>
    </div>
</div>
{% endblock %}
""",
    "answer_result.html": """{% extends 'base.html' %}
{% block title %}Resultado{% endblock %}
{% block content %}
<div class="row justify-content-center">
    <div class="col-md-8">
        <div class="card shadow p-4 text-center">
            <h3>Resultado da Correção</h3>
            <p><strong>Nota:</strong> {{ score }}</p>
            <p><strong>Feedback:</strong> {{ feedback }}</p>
            <a href="{{ url_for('main.dashboard') }}" class="btn btn-primary">Voltar ao Dashboard</a>
        </div>
    </div>
</div>
{% endblock %}
""",
}

# ==== FAVICON (ícone profissional, pode trocar por outro depois se quiser) ====
favicon_bytes = bytes([
    0x00,0x00,0x01,0x00,0x01,0x00,0x10,0x10,0x00,0x00,0x01,0x00,0x04,0x00,0x28,0x01,
    0x00,0x00,0x16,0x00,0x00,0x00,0x28,0x00,0x00,0x00,0x10,0x00,0x00,0x00,0x20,0x00,
    0x00,0x00,0x01,0x00,0x04,0x00,0x00,0x00,0x00,0x00,0x80,0x01,0x00,0x00,0x12,0x0B,
    0x00,0x00,0x12,0x0B,0x00,0x00,0x10,0x00,0x00,0x00,0x10,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
    0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00,
])

def write_file(path, content, binary=False):
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder, exist_ok=True)
    mode = "wb" if binary else "w"
    with open(path, mode, encoding=None if binary else "utf-8") as f:
        f.write(content)

print("Criando estrutura do projeto...")

# Arquivos principais
for path, content in files.items():
    write_file(path, content)
    print(f"Criado: {path}")

# Templates
for filename, content in templates.items():
    path = os.path.join("app", "templates", filename)
    write_file(path, content)
    print(f"Criado: {path}")

# Favicon
write_file("app/static/favicon.ico", favicon_bytes, binary=True)
print("Criado: app/static/favicon.ico")

print("\nEstrutura pronta!")
print("1. Crie e ative o ambiente virtual e instale as dependências:")
print("   python -m venv venv && source venv/bin/activate && pip install -r requirements.txt")
print("2. Copie .env.example para .env e edite as configurações.")
print("3. Inicialize o banco: flask db init; flask db migrate -m 'Inicial'; flask db upgrade")
print("4. Execute com: flask run ou python app.py")
print("5. Use git add, commit e push para subir ao GitHub!")