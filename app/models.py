from datetime import datetime
from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class Empresa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    ativa = db.Column(db.Boolean, default=True)

    notas = db.relationship('NotaFiscal', backref='empresa', lazy=True)


class Transportadora(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    ativa = db.Column(db.Boolean, default=True)

    notas = db.relationship('NotaFiscal', backref='transportadora', lazy=True)


class NotaFiscal(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero_nf = db.Column(db.String(50), nullable=False)
    numero_empenho = db.Column(db.String(50))
    cidade_destino = db.Column(db.String(120))
    estado_destino = db.Column(db.String(2))
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    data_previsao_entrega = db.Column(db.DateTime)

    valor_frete_estimado = db.Column(db.Float)

    situacao = db.Column(db.String(20), default='andamento')  # andamento ou finalizado

    empresa_id = db.Column(db.Integer, db.ForeignKey('empresa.id'), nullable=False)
    transportadora_id = db.Column(db.Integer, db.ForeignKey('transportadora.id'), nullable=False)

    historicos = db.relationship('HistoricoStatus', backref='nota_fiscal', lazy=True)
    


class HistoricoStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    status = db.Column(db.String(100), nullable=False)
    observacao = db.Column(db.Text)
    data_atualizacao = db.Column(db.DateTime, default=datetime.utcnow)

    nota_fiscal_id = db.Column(db.Integer, db.ForeignKey('nota_fiscal.id'), nullable=False)

    from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash


class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)

    nome = db.Column(db.String(120), nullable=False)
    usuario = db.Column(db.String(80), unique=True, nullable=False)
    senha_hash = db.Column(db.String(200), nullable=False)

    admin = db.Column(db.Boolean, default=False)

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def check_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)