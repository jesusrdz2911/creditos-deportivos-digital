"""Acceso a la base de datos SQLite y datos simulados."""
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from flask import current_app, g
from werkzeug.security import generate_password_hash


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript((Path(__file__).parent / "schema.sql").read_text(encoding="utf-8"))
    db.commit()


def seed_db():
    """Datos 100 % simulados: ninguna persona ni número de control es real."""
    db = get_db()
    pw = generate_password_hash("demo1234")
    usuarios = [
        ("Promotor Demo Uno", "promotor1@demo.test", "promotor", None),
        ("Promotor Demo Dos", "promotor2@demo.test", "promotor", None),
        ("Escolares Demo", "escolares@demo.test", "escolares", None),
        ("Estudiante Demo A", "alumno1@demo.test", "estudiante", "SIM0001"),
        ("Estudiante Demo B", "alumno2@demo.test", "estudiante", "SIM0002"),
        ("Estudiante Demo C", "alumno3@demo.test", "estudiante", "SIM0003"),
        ("Estudiante Demo D", "alumno4@demo.test", "estudiante", "SIM0004"),
    ]
    for nombre, email, rol, nc in usuarios:
        db.execute(
            "INSERT INTO usuario (nombre,email,password_hash,rol,no_control) VALUES (?,?,?,?,?)",
            (nombre, email, pw, rol, nc),
        )
    actividades = [
        ("Fútbol", "Ene-Jun 2027", "Lun y Mié 16:00-17:30", 3, 10, 80, 1),
        ("Voleibol", "Ene-Jun 2027", "Mar y Jue 15:00-16:30", 20, 10, 80, 2),
        ("Atletismo", "Ene-Jun 2027", "Vie 14:00-16:00", 20, 8, 80, 2),
    ]
    for a in actividades:
        db.execute(
            "INSERT INTO actividad (nombre,periodo,horario,cupo,sesiones_totales,minimo_pct,promotor_id)"
            " VALUES (?,?,?,?,?,?,?)",
            a,
        )
    # Los alumnos A, B y C ya están inscritos en Fútbol (cupo 3, queda lleno).
    hoy = date.today()
    for est in (4, 5, 6):
        db.execute(
            "INSERT INTO inscripcion (estudiante_id,actividad_id,creada_en) VALUES (?,?,?)",
            (est, 1, hoy.isoformat()),
        )
    # 10 sesiones ya registradas. A asiste a 9 (90 %), B a 8 (80 %), C a 5 (50 %).
    for i in range(10):
        f = (hoy - timedelta(days=70 - i * 7)).isoformat()
        sid = db.execute("INSERT INTO sesion (actividad_id,fecha) VALUES (1,?)", (f,)).lastrowid
        db.execute("INSERT INTO asistencia VALUES (?,?,?)", (sid, 4, 1 if i < 9 else 0))
        db.execute("INSERT INTO asistencia VALUES (?,?,?)", (sid, 5, 1 if i < 8 else 0))
        db.execute("INSERT INTO asistencia VALUES (?,?,?)", (sid, 6, 1 if i < 5 else 0))
    db.commit()
