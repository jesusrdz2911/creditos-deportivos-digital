"""Rutas de la plataforma, agrupadas por rol."""
import secrets
from functools import wraps

from flask import (Blueprint, Response, abort, current_app, flash, g, redirect,
                   render_template, request, session, url_for)
from werkzeug.security import check_password_hash

from . import services
from .db import get_db
from .pdf import constancia_pdf

bp = Blueprint("main", __name__)


# --- Sesión, CSRF y roles -------------------------------------------------------
@bp.before_app_request
def cargar_usuario():
    uid = session.get("uid")
    g.user = None
    if uid is not None:
        g.user = get_db().execute("SELECT * FROM usuario WHERE id=?", (uid,)).fetchone()


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


@bp.before_app_request
def verificar_csrf():
    if request.method == "POST" and not current_app.config.get("TESTING_SIN_CSRF"):
        if not secrets.compare_digest(request.form.get("csrf", ""), session.get("csrf", "x")):
            abort(400, "Formulario inválido o vencido. Recarga la página.")


@bp.app_context_processor
def inyectar():
    return {"csrf_token": csrf_token, "user": g.get("user")}


def rol_requerido(*roles):
    def deco(fn):
        @wraps(fn)
        def envuelta(*a, **kw):
            if g.user is None:
                return redirect(url_for("main.login"))
            if g.user["rol"] not in roles:
                abort(403)
            return fn(*a, **kw)
        return envuelta
    return deco


HOME = {"estudiante": "main.actividades", "promotor": "main.promotor_home", "escolares": "main.escolares"}


@bp.route("/")
def inicio():
    if g.user:
        return redirect(url_for(HOME[g.user["rol"]]))
    return redirect(url_for("main.login"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = get_db().execute("SELECT * FROM usuario WHERE email=?",
                             (request.form.get("email", "").strip().lower(),)).fetchone()
        if u and check_password_hash(u["password_hash"], request.form.get("password", "")):
            session.clear()
            session["uid"] = u["id"]
            return redirect(url_for(HOME[u["rol"]]))
        flash("Correo o contraseña incorrectos.", "error")
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("main.login"))


# --- Estudiante -------------------------------------------------------------------
@bp.route("/actividades", methods=["GET", "POST"])
@rol_requerido("estudiante")
def actividades():
    db = get_db()
    if request.method == "POST":
        try:
            services.inscribir(db, g.user["id"], int(request.form.get("actividad_id", 0)))
            flash("Inscripción realizada.", "ok")
        except (services.ReglaError, ValueError) as e:
            flash(str(e) if isinstance(e, services.ReglaError) else "Actividad inválida.", "error")
        return redirect(url_for("main.actividades"))
    filas = db.execute(
        "SELECT a.*, p.nombre AS promotor, "
        "(SELECT COUNT(*) FROM inscripcion i WHERE i.actividad_id=a.id) AS usados, "
        "(SELECT COUNT(*) FROM inscripcion i WHERE i.actividad_id=a.id AND i.estudiante_id=?) AS inscrito "
        "FROM actividad a JOIN usuario p ON p.id=a.promotor_id ORDER BY a.nombre",
        (g.user["id"],),
    ).fetchall()
    return render_template("actividades.html", actividades=filas)


@bp.route("/mis-actividades")
@rol_requerido("estudiante")
def mis_actividades():
    db = get_db()
    filas = db.execute(
        "SELECT i.id AS inscripcion_id, a.id AS actividad_id, a.nombre, a.periodo, a.horario, "
        "a.minimo_pct, a.sesiones_totales, p.nombre AS promotor, c.folio, "
        "(SELECT COUNT(*) FROM sesion s WHERE s.actividad_id=a.id) AS registradas "
        "FROM inscripcion i JOIN actividad a ON a.id=i.actividad_id "
        "JOIN usuario p ON p.id=a.promotor_id LEFT JOIN constancia c ON c.inscripcion_id=i.id "
        "WHERE i.estudiante_id=? ORDER BY a.nombre",
        (g.user["id"],),
    ).fetchall()
    items = [dict(f, pct=services.porcentaje(db, g.user["id"], f["actividad_id"])) for f in filas]
    return render_template("mis_actividades.html", items=items)


@bp.route("/constancia/<folio>.pdf")
def constancia_descarga(folio):
    if g.user is None:
        return redirect(url_for("main.login"))
    db = get_db()
    r = services.verificar(db, folio, current_app.config["SELLO_SECRET"])
    if r is None:
        abort(404)
    dueno = db.execute(
        "SELECT i.estudiante_id, a.promotor_id FROM constancia c "
        "JOIN inscripcion i ON i.id=c.inscripcion_id JOIN actividad a ON a.id=i.actividad_id "
        "WHERE c.folio=?", (r["datos"]["folio"],)).fetchone()
    permitido = (g.user["rol"] == "escolares" or g.user["id"] in (dueno["estudiante_id"], dueno["promotor_id"]))
    if not permitido:
        abort(403)
    pdf = constancia_pdf(r["datos"], current_app.config["BASE_URL"])
    return Response(pdf, mimetype="application/pdf",
                    headers={"Content-Disposition": f"inline; filename={r['datos']['folio']}.pdf"})


# --- Promotor ---------------------------------------------------------------------
@bp.route("/promotor")
@rol_requerido("promotor")
def promotor_home():
    filas = get_db().execute(
        "SELECT a.*, (SELECT COUNT(*) FROM inscripcion i WHERE i.actividad_id=a.id) AS inscritos, "
        "(SELECT COUNT(*) FROM sesion s WHERE s.actividad_id=a.id) AS registradas "
        "FROM actividad a WHERE a.promotor_id=? ORDER BY a.nombre", (g.user["id"],)).fetchall()
    return render_template("promotor_home.html", actividades=filas)


def _actividad_propia(db, actividad_id):
    a = db.execute("SELECT * FROM actividad WHERE id=?", (actividad_id,)).fetchone()
    if a is None:
        abort(404)
    if a["promotor_id"] != g.user["id"]:
        abort(403)
    return a


@bp.route("/promotor/actividad/<int:actividad_id>", methods=["GET", "POST"])
@rol_requerido("promotor")
def promotor_actividad(actividad_id):
    db = get_db()
    act = _actividad_propia(db, actividad_id)
    if request.method == "POST":
        accion = request.form.get("accion")
        try:
            if accion == "sesion":
                presentes = {int(x) for x in request.form.getlist("presente")}
                services.registrar_sesion(db, actividad_id, request.form.get("fecha", ""), presentes)
                flash("Lista de asistencia guardada.", "ok")
            elif accion == "constancia":
                c = services.emitir_constancia(db, int(request.form["inscripcion_id"]),
                                               g.user["id"], current_app.config["SELLO_SECRET"])
                flash(f"Constancia emitida con folio {c['folio']}.", "ok")
        except (services.ReglaError, ValueError) as e:
            flash(str(e) if isinstance(e, services.ReglaError) else "Datos inválidos.", "error")
        return redirect(url_for("main.promotor_actividad", actividad_id=actividad_id))
    inscritos = db.execute(
        "SELECT i.id AS inscripcion_id, u.id AS estudiante_id, u.nombre, u.no_control, c.folio "
        "FROM inscripcion i JOIN usuario u ON u.id=i.estudiante_id "
        "LEFT JOIN constancia c ON c.inscripcion_id=i.id WHERE i.actividad_id=? ORDER BY u.nombre",
        (actividad_id,)).fetchall()
    alumnos = [dict(r, pct=services.porcentaje(db, r["estudiante_id"], actividad_id),
                    cumple=services.porcentaje(db, r["estudiante_id"], actividad_id) >= act["minimo_pct"])
               for r in inscritos]
    registradas = db.execute("SELECT COUNT(*) FROM sesion WHERE actividad_id=?", (actividad_id,)).fetchone()[0]
    from datetime import date
    return render_template("promotor_actividad.html", act=act, alumnos=alumnos,
                           registradas=registradas, hoy=date.today().isoformat())


# --- Servicios Escolares ----------------------------------------------------------
@bp.route("/escolares", methods=["GET", "POST"])
@rol_requerido("escolares")
def escolares():
    if request.method == "POST":
        folio = request.form.get("folio", "").strip()
        if not folio:
            flash("Escribe un folio.", "error")
            return redirect(url_for("main.escolares"))
        return redirect(url_for("main.verificar", folio=folio))
    filas = get_db().execute(
        "SELECT c.folio, c.emitida_en, c.porcentaje, u.nombre, a.nombre AS actividad "
        "FROM constancia c JOIN inscripcion i ON i.id=c.inscripcion_id "
        "JOIN usuario u ON u.id=i.estudiante_id JOIN actividad a ON a.id=i.actividad_id "
        "ORDER BY c.emitida_en DESC").fetchall()
    return render_template("escolares.html", constancias=filas)


# --- Público: verificación del QR ---------------------------------------------------
@bp.route("/verificar/<folio>")
def verificar(folio):
    r = services.verificar(get_db(), folio, current_app.config["SELLO_SECRET"])
    return render_template("verificar.html", folio=folio, r=r), (200 if r else 404)
