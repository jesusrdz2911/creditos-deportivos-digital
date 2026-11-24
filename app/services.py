"""Reglas de negocio: inscripción, porcentaje, acreditación, folio y sello digital."""
import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime


class ReglaError(Exception):
    """Una regla de negocio no se cumple; el mensaje se muestra al usuario."""


def ahora():
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


# --- Inscripción (RN: sin duplicados y sin exceder el cupo) -------------------
def inscribir(db, estudiante_id, actividad_id):
    act = db.execute("SELECT * FROM actividad WHERE id=?", (actividad_id,)).fetchone()
    if act is None:
        raise ReglaError("La actividad no existe.")
    ya = db.execute(
        "SELECT 1 FROM inscripcion WHERE estudiante_id=? AND actividad_id=?",
        (estudiante_id, actividad_id),
    ).fetchone()
    if ya:
        raise ReglaError("Ya estás inscrito en esta actividad.")
    usados = db.execute(
        "SELECT COUNT(*) FROM inscripcion WHERE actividad_id=?", (actividad_id,)
    ).fetchone()[0]
    if usados >= act["cupo"]:
        raise ReglaError("La actividad ya no tiene cupo.")
    db.execute(
        "INSERT INTO inscripcion (estudiante_id,actividad_id,creada_en) VALUES (?,?,?)",
        (estudiante_id, actividad_id, ahora()),
    )
    db.commit()


# --- Asistencia y porcentaje ---------------------------------------------------
def porcentaje(db, estudiante_id, actividad_id):
    """Sesiones con asistencia entre las sesiones planeadas del curso, en %."""
    act = db.execute(
        "SELECT sesiones_totales FROM actividad WHERE id=?", (actividad_id,)
    ).fetchone()
    presentes = db.execute(
        "SELECT COUNT(*) FROM asistencia a JOIN sesion s ON s.id=a.sesion_id "
        "WHERE s.actividad_id=? AND a.estudiante_id=? AND a.presente=1",
        (actividad_id, estudiante_id),
    ).fetchone()[0]
    return round(presentes * 100.0 / act["sesiones_totales"], 2)


def registrar_sesion(db, actividad_id, fecha, presentes_ids):
    """Crea la sesión del día y guarda la lista. Una fecha no se repite."""
    try:
        datetime.strptime(fecha, "%Y-%m-%d")
    except ValueError:
        raise ReglaError("La fecha no es válida.")
    act = db.execute("SELECT sesiones_totales FROM actividad WHERE id=?", (actividad_id,)).fetchone()
    registradas = db.execute(
        "SELECT COUNT(*) FROM sesion WHERE actividad_id=?", (actividad_id,)
    ).fetchone()[0]
    if registradas >= act["sesiones_totales"]:
        raise ReglaError("Ya se registraron todas las sesiones planeadas.")
    inscritos = [
        r["estudiante_id"]
        for r in db.execute("SELECT estudiante_id FROM inscripcion WHERE actividad_id=?", (actividad_id,))
    ]
    try:
        sid = db.execute(
            "INSERT INTO sesion (actividad_id,fecha) VALUES (?,?)", (actividad_id, fecha)
        ).lastrowid
    except sqlite3.IntegrityError:
        raise ReglaError("Ya existe una sesión registrada en esa fecha.")
    for est in inscritos:
        db.execute(
            "INSERT INTO asistencia (sesion_id,estudiante_id,presente) VALUES (?,?,?)",
            (sid, est, 1 if est in presentes_ids else 0),
        )
    db.commit()
    return sid


# --- Constancia: folio, sello y emisión -----------------------------------------
def _canonico(c):
    return "|".join(
        [c["folio"], c["nombre"], c["no_control"] or "", c["actividad"], c["periodo"],
         f"{c['porcentaje']:.2f}", c["promotor"], c["emitida_en"]]
    )


def calcular_sello(datos, secreto):
    return hmac.new(secreto.encode(), _canonico(datos).encode(), hashlib.sha256).hexdigest()


def _datos_constancia(db, inscripcion_id):
    return db.execute(
        "SELECT c.folio, c.porcentaje, c.emitida_en, c.sello, c.id AS constancia_id, "
        "u.nombre, u.no_control, a.nombre AS actividad, a.periodo, p.nombre AS promotor "
        "FROM constancia c JOIN inscripcion i ON i.id=c.inscripcion_id "
        "JOIN usuario u ON u.id=i.estudiante_id JOIN actividad a ON a.id=i.actividad_id "
        "JOIN usuario p ON p.id=c.autorizada_por WHERE c.inscripcion_id=?",
        (inscripcion_id,),
    ).fetchone()


def emitir_constancia(db, inscripcion_id, promotor_id, secreto):
    row = db.execute(
        "SELECT i.id, i.estudiante_id, a.id AS actividad_id, a.promotor_id, a.minimo_pct, "
        "u.nombre, u.no_control, a.nombre AS actividad, a.periodo, p.nombre AS promotor "
        "FROM inscripcion i JOIN actividad a ON a.id=i.actividad_id "
        "JOIN usuario u ON u.id=i.estudiante_id JOIN usuario p ON p.id=a.promotor_id "
        "WHERE i.id=?",
        (inscripcion_id,),
    ).fetchone()
    if row is None:
        raise ReglaError("La inscripción no existe.")
    if row["promotor_id"] != promotor_id:
        raise ReglaError("Solo el promotor de la actividad puede autorizar su constancia.")
    if _datos_constancia(db, inscripcion_id) is not None:
        raise ReglaError("Esta constancia ya fue emitida.")
    pct = porcentaje(db, row["estudiante_id"], row["actividad_id"])
    if pct < row["minimo_pct"]:
        raise ReglaError(f"No alcanza el mínimo: {pct:.0f} % de {row['minimo_pct']} % requerido.")
    emitida = ahora()
    for _ in range(5):  # reintenta si el folio aleatorio coincidiera
        folio = f"CCD-{datetime.now().year}-{secrets.token_hex(3).upper()}"
        datos = {
            "folio": folio, "nombre": row["nombre"], "no_control": row["no_control"],
            "actividad": row["actividad"], "periodo": row["periodo"], "porcentaje": pct,
            "promotor": row["promotor"], "emitida_en": emitida,
        }
        try:
            db.execute(
                "INSERT INTO constancia (inscripcion_id,folio,porcentaje,emitida_en,autorizada_por,sello)"
                " VALUES (?,?,?,?,?,?)",
                (inscripcion_id, folio, pct, emitida, promotor_id, calcular_sello(datos, secreto)),
            )
            db.commit()
            return _datos_constancia(db, inscripcion_id)
        except sqlite3.IntegrityError:
            db.rollback()
            if _datos_constancia(db, inscripcion_id) is not None:
                raise ReglaError("Esta constancia ya fue emitida.")
    raise ReglaError("No se pudo generar un folio único; intenta de nuevo.")


def verificar(db, folio, secreto):
    """Recalcula el sello con lo guardado en la base y lo compara con el sello emitido."""
    c = db.execute(
        "SELECT i.id FROM constancia c JOIN inscripcion i ON i.id=c.inscripcion_id WHERE c.folio=?",
        (folio.strip().upper(),),
    ).fetchone()
    if c is None:
        return None
    datos = _datos_constancia(db, c["id"])
    esperado = calcular_sello(datos, secreto)
    return {"datos": datos, "valida": hmac.compare_digest(esperado, datos["sello"])}
