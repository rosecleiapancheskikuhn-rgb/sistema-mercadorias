from flask_login import login_required, login_user
from flask_login import current_user
from flask import Blueprint, render_template, request, redirect, url_for
from datetime import datetime, date
from app import db
from app.models import Empresa, Transportadora, NotaFiscal, HistoricoStatus, Usuario
from flask_login import logout_user

main = Blueprint('main', __name__)
print("ROUTES CARREGADAS COM SUCESSO")

# ==========================================
# FLUXO OFICIAL DE STATUS
# ==========================================

STATUS_FLUXO = [
    "Emitida",
    "Recebida pela Transportadora",
    "Em Depósito",
    "Em Transporte",
    "Em Rota de Entrega",
    "Entregue"
]
from functools import wraps
from flask import abort

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# LOGIN
# ==========================================

from flask_login import current_user

@main.route("/", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("main.home"))

    if request.method == "POST":
        usuario_digitado = request.form.get("usuario")
        senha_digitada = request.form.get("senha")

        usuario = Usuario.query.filter_by(usuario=usuario_digitado).first()

        if usuario and usuario.check_senha(senha_digitada):
            login_user(usuario)
            return redirect(url_for("main.home"))

    return render_template("login.html")

@main.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("main.login"))


# ==========================================
# DASHBOARD
# ==========================================

@main.route("/dashboard")
@login_required
def home():
    return render_template("home.html")


# ==========================================
# EMPRESAS
# ==========================================

@main.route("/empresas")
@login_required
def listar_empresas():
    empresas = Empresa.query.order_by(Empresa.nome).all()
    return render_template("empresas.html", empresas=empresas)


@main.route("/empresas/nova", methods=["GET", "POST"])
@login_required
def nova_empresa():
    if request.method == "POST":
        nome = request.form.get("nome")

        if nome:
            empresa = Empresa(nome=nome)
            db.session.add(empresa)
            db.session.commit()
            return redirect(url_for("main.listar_empresas"))

    return render_template("nova_empresa.html")


# ==========================================
# TRANSPORTADORAS
# ==========================================

@main.route("/transportadoras")
@login_required
def listar_transportadoras():
    transportadoras = Transportadora.query.order_by(Transportadora.nome).all()
    return render_template("transportadoras.html", transportadoras=transportadoras)


@main.route("/transportadoras/nova", methods=["GET", "POST"])
@login_required
def nova_transportadora():
    if request.method == "POST":
        nome = request.form.get("nome")

        if nome:
            transportadora = Transportadora(nome=nome)
            db.session.add(transportadora)
            db.session.commit()
            return redirect(url_for("main.listar_transportadoras"))

    return render_template("nova_transportadora.html")


# ==========================================
# NOTAS EM ANDAMENTO
# ==========================================

@main.route("/notas")
@login_required
def listar_notas():

    empresa_id = request.args.get("empresa")
    transportadora_id = request.args.get("transportadora")
    numero_nf = request.args.get("numero_nf")
    numero_empenho = request.args.get("numero_empenho")

    query = NotaFiscal.query.filter_by(situacao='andamento')

    if empresa_id:
        query = query.filter_by(empresa_id=empresa_id)

    if transportadora_id:
        query = query.filter_by(transportadora_id=transportadora_id)

    if numero_nf:
        query = query.filter(NotaFiscal.numero_nf.contains(numero_nf))

    if numero_empenho:
        query = query.filter(NotaFiscal.numero_empenho.contains(numero_empenho))

    notas = query.order_by(NotaFiscal.data_criacao.desc()).all()

    empresas = Empresa.query.order_by(Empresa.nome).all()
    transportadoras = Transportadora.query.order_by(Transportadora.nome).all()

    STATUS_FLUXO = [
        "Emitida",
        "Recebida pela Transportadora",
        "Em Depósito",
        "Em Transporte",
        "Em Rota de Entrega",
        "Entregue"
    ]

    notas_com_status = []
    total_problemas = 0
    total_proximas = 0
    hoje = date.today()

    for nota in notas:

        historicos = HistoricoStatus.query.filter_by(
            nota_fiscal_id=nota.id
        ).order_by(
            HistoricoStatus.data_atualizacao.desc()
        ).all()

        # PROBLEMA
        problema_aberto = False
        for h in historicos:
            if h.status == "Problema":
                problema_aberto = True
                break
            if h.status == "Problema Resolvido":
                break

        if problema_aberto:
            total_problemas += 1

        # STATUS REAL DO FLUXO
        status_atual = None
        for h in historicos:
            if h.status in STATUS_FLUXO:
                status_atual = h.status
                break

        # PRÓXIMAS 48H
        alerta_proximo = False
        if nota.data_previsao_entrega:
            dias_restantes = (nota.data_previsao_entrega.date() - hoje).days
            if 0 <= dias_restantes <= 2:
                alerta_proximo = True
                total_proximas += 1

        notas_com_status.append({
            "nota": nota,
            "status_atual": status_atual,
            "alerta_proximo": alerta_proximo,
            "problema_aberto": problema_aberto
        })

    return render_template(
        "notas.html",
        notas=notas_com_status,
        total_andamento=len(notas_com_status),
        total_problemas=total_problemas,
        total_proximas=total_proximas,
        empresas=empresas,
        transportadoras=transportadoras
    )


# ==========================================
# DETALHE DA NOTA
# ==========================================

@main.route("/notas/<int:nota_id>")
@login_required
def detalhe_nota(nota_id):

    nota = NotaFiscal.query.get_or_404(nota_id)

    historicos = HistoricoStatus.query.filter_by(
        nota_fiscal_id=nota.id
    ).order_by(
        HistoricoStatus.data_atualizacao.desc()
    ).all()

    # ==========================================
    # FLUXO OFICIAL
    # ==========================================

    STATUS_FLUXO = [
        "Emitida",
        "Recebida pela Transportadora",
        "Em Depósito",
        "Em Transporte",
        "Em Rota de Entrega",
        "Entregue"
    ]

    # ==========================================
    # STATUS ATUAL (IGNORA PROBLEMA)
    # ==========================================

    status_atual = None

    for h in historicos:
        if h.status in STATUS_FLUXO:
            status_atual = h.status
            break

    # ==========================================
    # VERIFICAR SE EXISTE PROBLEMA ATIVO
    # ==========================================

    problema_ativo = any(h.status == "Problema" for h in historicos)

    # ==========================================
    # PRÓXIMO STATUS
    # ==========================================

    proximo_status = None

    if status_atual in STATUS_FLUXO:
        indice = STATUS_FLUXO.index(status_atual)
        if indice + 1 < len(STATUS_FLUXO):
            proximo_status = STATUS_FLUXO[indice + 1]

    return render_template(
        "detalhe_nota.html",
        nota=nota,
        historicos=historicos,
        status_atual=status_atual,
        proximo_status=proximo_status,
        problema_ativo=problema_ativo
    )


# ==========================================
# AVANÇAR STATUS
# ==========================================

@main.route("/notas/<int:nota_id>/avancar", methods=["POST"])
@login_required
def avancar_status(nota_id):

    nota = NotaFiscal.query.get_or_404(nota_id)

    STATUS_FLUXO = [
        "Emitida",
        "Recebida pela Transportadora",
        "Em Depósito",
        "Em Transporte",
        "Em Rota de Entrega",
        "Entregue"
    ]

    # Buscar todos históricos
    historicos = HistoricoStatus.query.filter_by(
        nota_fiscal_id=nota.id
    ).order_by(
        HistoricoStatus.data_atualizacao.desc()
    ).all()

    # Encontrar último status válido (ignorar Problema)
    status_atual = None

    for h in historicos:
        if h.status in STATUS_FLUXO:
            status_atual = h.status
            break

    if status_atual in STATUS_FLUXO:
        indice = STATUS_FLUXO.index(status_atual)

        if indice + 1 < len(STATUS_FLUXO):

            novo_status = STATUS_FLUXO[indice + 1]

            db.session.add(HistoricoStatus(
                status=novo_status,
                nota_fiscal_id=nota.id
            ))

            if novo_status == "Entregue":
                nota.situacao = "finalizado"

            db.session.commit()

    return redirect(url_for("main.detalhe_nota", nota_id=nota.id))


# ==========================================
# REGISTRAR PROBLEMA
# ==========================================

@main.route("/notas/<int:nota_id>/problema", methods=["POST"])
@login_required
def registrar_problema(nota_id):

    nota = NotaFiscal.query.get_or_404(nota_id)

    observacao = request.form.get("observacao")

    db.session.add(HistoricoStatus(
        status="Problema",
        observacao=observacao,
        nota_fiscal_id=nota.id
    ))

    db.session.commit()

    return redirect(url_for("main.detalhe_nota", nota_id=nota.id))

# ==========================================
# RESOLVER PROBLEMA
# ==========================================

@main.route("/notas/<int:nota_id>/resolver_problema", methods=["POST"])
@login_required
def resolver_problema(nota_id):

    nota = NotaFiscal.query.get_or_404(nota_id)

    # Verificar se existe problema em aberto
    ultimo = HistoricoStatus.query.filter_by(
        nota_fiscal_id=nota.id
    ).order_by(
        HistoricoStatus.data_atualizacao.desc()
    ).first()

    if ultimo and ultimo.status == "Problema":

        db.session.add(HistoricoStatus(
            status="Problema Resolvido",
            nota_fiscal_id=nota.id
        ))

        db.session.commit()

    return redirect(url_for("main.detalhe_nota", nota_id=nota.id))

# ==========================================
# NOVA NOTA
# ==========================================

@main.route("/notas/nova", methods=["GET", "POST"])
@login_required
def nova_nota():

    empresas = Empresa.query.filter_by(ativa=True).order_by(Empresa.nome).all()
    transportadoras = Transportadora.query.filter_by(ativa=True).order_by(Transportadora.nome).all()

    if request.method == "POST":

        numero_nf = request.form.get("numero_nf")
        numero_empenho = request.form.get("numero_empenho")
        empresa_id = request.form.get("empresa_id")
        transportadora_id = request.form.get("transportadora_id")
        valor_frete = request.form.get("valor_frete")
        data_previsao = request.form.get("data_previsao")
        cidade_destino = request.form.get("cidade_destino")
        estado_destino = request.form.get("estado_destino")

        valor_convertido = None
        if valor_frete:
            valor_tratado = valor_frete.replace(".", "").replace(",", ".")
            try:
                valor_convertido = float(valor_tratado)
            except ValueError:
                valor_convertido = None

        if numero_nf and empresa_id and transportadora_id:

            nova_nota = NotaFiscal(
                numero_nf=numero_nf,
                numero_empenho=numero_empenho,
                cidade_destino=cidade_destino,
                estado_destino=estado_destino,
                empresa_id=empresa_id,
                transportadora_id=transportadora_id,
                valor_frete_estimado=valor_convertido,
                data_previsao_entrega=datetime.strptime(data_previsao, "%Y-%m-%d") if data_previsao else None
            )

            db.session.add(nova_nota)
            db.session.commit()

            db.session.add(HistoricoStatus(
                status="Emitida",
                nota_fiscal_id=nova_nota.id
            ))

            db.session.commit()

            return redirect(url_for("main.listar_notas"))

    return render_template(
        "nova_nota.html",
        empresas=empresas,
        transportadoras=transportadoras
    )



# ==========================================
# FINALIZADAS
# ==========================================

@main.route("/notas/finalizadas")
@login_required
def listar_notas_finalizadas():

    notas = NotaFiscal.query.filter_by(
        situacao='finalizado'
    ).order_by(
        NotaFiscal.data_criacao.desc()
    ).all()

    return render_template("notas_finalizadas.html", notas=notas)

    # ==========================================
# USUÁRIOS (ADMIN)
# ==========================================

@main.route("/usuarios")
@login_required
@admin_required
def listar_usuarios():
    usuarios = Usuario.query.order_by(Usuario.nome).all()
    return render_template("usuarios.html", usuarios=usuarios)


@main.route("/usuarios/novo", methods=["GET", "POST"])
@login_required
@admin_required
def novo_usuario():

    if request.method == "POST":
        nome = request.form.get("nome")
        usuario_login = request.form.get("usuario")
        senha = request.form.get("senha")
        admin_flag = True if request.form.get("admin") == "on" else False

        if nome and usuario_login and senha:

            if Usuario.query.filter_by(usuario=usuario_login).first():
                return "Usuário já existe"

            novo = Usuario(
                nome=nome,
                usuario=usuario_login,
                admin=admin_flag
            )
            novo.set_senha(senha)

            db.session.add(novo)
            db.session.commit()

            return redirect(url_for("main.listar_usuarios"))

    return render_template("novo_usuario.html")

# ==========================================
# EDITAR USUÁRIO
# ==========================================

@main.route("/usuarios/<int:usuario_id>/editar", methods=["GET", "POST"])
@login_required
@admin_required
def editar_usuario(usuario_id):

    usuario = Usuario.query.get_or_404(usuario_id)

    if request.method == "POST":

        usuario.nome = request.form.get("nome")
        usuario.usuario = request.form.get("usuario")

        # Atualizar senha apenas se for preenchida
        nova_senha = request.form.get("senha")
        if nova_senha:
            usuario.set_senha(nova_senha)

        usuario.admin = True if request.form.get("admin") == "on" else False

        db.session.commit()

        return redirect(url_for("main.listar_usuarios"))

    return render_template("editar_usuario.html", usuario=usuario)

# ==========================================
# EXCLUIR USUÁRIO
# ==========================================

@main.route("/usuarios/<int:usuario_id>/excluir", methods=["POST"])
@login_required
@admin_required
def excluir_usuario(usuario_id):

    usuario = Usuario.query.get_or_404(usuario_id)

    # Impedir que o admin exclua a si mesmo
    if usuario.id == current_user.id:
        return "Você não pode excluir seu próprio usuário."

    db.session.delete(usuario)
    db.session.commit()

    return redirect(url_for("main.listar_usuarios"))

# ==========================================
# PAINEL TV
# ==========================================

@main.route("/painel")
@login_required
def painel():

    idx = request.args.get("idx", default=0, type=int)

    STATUS_FLUXO = [
        "Emitida",
        "Recebida pela Transportadora",
        "Em Depósito",
        "Em Transporte",
        "Em Rota de Entrega",
        "Entregue"
    ]

    notas = NotaFiscal.query.filter_by(
        situacao='andamento'
    ).order_by(
        NotaFiscal.data_criacao.desc()
    ).all()

    notas_painel = []
    total_problemas = 0
    total_proximas = 0

    hoje = date.today()

    for nota in notas:

        historicos = HistoricoStatus.query.filter_by(
            nota_fiscal_id=nota.id
        ).order_by(
            HistoricoStatus.data_atualizacao.desc()
        ).all()

        # ===============================
        # IDENTIFICAR PROBLEMA (PARALELO)
        # ===============================
        problema_aberto = False
        for h in historicos:
            if h.status == "Problema":
                problema_aberto = True
                break
            if h.status == "Problema Resolvido":
                break

        if problema_aberto:
            total_problemas += 1

        # ===============================
        # IDENTIFICAR STATUS REAL DO FLUXO
        # ===============================
        status_atual = None
        for h in historicos:
            if h.status in STATUS_FLUXO:
                status_atual = h.status
                break

        # ===============================
        # ATRASO / PRÓXIMA
        # ===============================
        atrasada = False
        alerta_proximo = False

        if nota.data_previsao_entrega:
            dias = (nota.data_previsao_entrega.date() - hoje).days

            if dias < 0:
                atrasada = True
            elif 0 <= dias <= 2:
                alerta_proximo = True
                total_proximas += 1

        # ===============================
        # DEFINIR PRIORIDADE
        # ===============================
        if atrasada:
            prioridade = 1
        elif problema_aberto:
            prioridade = 2
        elif alerta_proximo:
            prioridade = 3
        else:
            prioridade = 4

        # ===============================
        # ÍNDICE DO FLUXO
        # ===============================
        if status_atual in STATUS_FLUXO:
            indice_status = STATUS_FLUXO.index(status_atual)
        else:
            indice_status = -1

        notas_painel.append({
            "nota": nota,
            "status_atual": status_atual,
            "indice_status": indice_status,
            "prioridade": prioridade,
            "alerta_proximo": alerta_proximo,
            "atrasada": atrasada,
            "problema_aberto": problema_aberto
        })

    notas_painel.sort(
        key=lambda x: (x["prioridade"], -x["nota"].data_criacao.timestamp())
    )

    if notas_painel:
        if idx >= len(notas_painel):
            idx = 0
        destaque = notas_painel[idx]
    else:
        destaque = None

    return render_template(
        "painel.html",
        notas=notas_painel,
        destaque=destaque,
        total_andamento=len(notas_painel),
        total_problemas=total_problemas,
        total_proximas=total_proximas
    )

