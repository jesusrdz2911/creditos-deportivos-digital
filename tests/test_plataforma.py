"""Casos de prueba. Cada uno cita el requerimiento o regla que verifica."""
import re

import pytest

from app import services
from tests.conftest import entrar

SECRETO = "secreto-de-prueba"


# --- Reglas de negocio ---------------------------------------------------------
def test_RN01_no_se_duplica_inscripcion(db):  # alumno 4 ya está en Fútbol
    with pytest.raises(services.ReglaError, match="Ya estás inscrito"):
        services.inscribir(db, 4, 1)


def test_RN02_no_se_excede_el_cupo(db):  # Fútbol: cupo 3 y ya hay 3
    with pytest.raises(services.ReglaError, match="cupo"):
        services.inscribir(db, 7, 1)


def test_RF_inscripcion_exitosa(db):
    services.inscribir(db, 7, 2)
    assert db.execute("SELECT COUNT(*) FROM inscripcion WHERE actividad_id=2").fetchone()[0] == 1


def test_RF_porcentaje_de_asistencia(db):
    assert services.porcentaje(db, 4, 1) == 90.0
    assert services.porcentaje(db, 5, 1) == 80.0
    assert services.porcentaje(db, 6, 1) == 50.0


def test_RN03_no_emite_si_no_alcanza_minimo(db):  # alumno 6 = 50 %
    insc = db.execute("SELECT id FROM inscripcion WHERE estudiante_id=6").fetchone()["id"]
    with pytest.raises(services.ReglaError, match="No alcanza el mínimo"):
        services.emitir_constancia(db, insc, 1, SECRETO)


def test_RN03_emite_justo_en_el_minimo(db):  # alumno 5 = 80 %, mínimo 80 %
    insc = db.execute("SELECT id FROM inscripcion WHERE estudiante_id=5").fetchone()["id"]
    c = services.emitir_constancia(db, insc, 1, SECRETO)
    assert c["folio"].startswith("CCD-")


def test_RN04_solo_el_promotor_de_la_actividad_autoriza(db):
    insc = db.execute("SELECT id FROM inscripcion WHERE estudiante_id=4").fetchone()["id"]
    with pytest.raises(services.ReglaError, match="Solo el promotor"):
        services.emitir_constancia(db, insc, 2, SECRETO)  # promotor 2 no es el de Fútbol


def test_RN05_constancia_no_se_emite_dos_veces(db):
    insc = db.execute("SELECT id FROM inscripcion WHERE estudiante_id=4").fetchone()["id"]
    services.emitir_constancia(db, insc, 1, SECRETO)
    with pytest.raises(services.ReglaError, match="ya fue emitida"):
        services.emitir_constancia(db, insc, 1, SECRETO)


def test_RN06_minimo_es_configurable(db):
    db.execute("UPDATE actividad SET minimo_pct=95 WHERE id=1")
    db.commit()
    insc = db.execute("SELECT id FROM inscripcion WHERE estudiante_id=4").fetchone()["id"]
    with pytest.raises(services.ReglaError):  # 90 % < 95 %
        services.emitir_constancia(db, insc, 1, SECRETO)


def test_RF_registrar_sesion_y_no_repetir_fecha(db):
    db.execute("UPDATE actividad SET sesiones_totales=12 WHERE id=1")
    db.commit()
    services.registrar_sesion(db, 1, "2027-03-01", {4})
    with pytest.raises(services.ReglaError, match="misma fecha|esa fecha"):
        services.registrar_sesion(db, 1, "2027-03-01", {4})


def test_RF_no_se_registran_mas_sesiones_que_las_planeadas(db):  # Fútbol: 10 de 10
    with pytest.raises(services.ReglaError, match="todas las sesiones"):
        services.registrar_sesion(db, 1, "2027-04-01", {4})


# --- Sello y verificación ----------------------------------------------------
def _emitir(db):
    insc = db.execute("SELECT id FROM inscripcion WHERE estudiante_id=4").fetchone()["id"]
    return services.emitir_constancia(db, insc, 1, SECRETO)


def test_RF_verificacion_valida(db):
    c = _emitir(db)
    r = services.verificar(db, c["folio"], SECRETO)
    assert r["valida"] is True


def test_RF_verificacion_detecta_alteracion(db):
    c = _emitir(db)
    db.execute("UPDATE constancia SET porcentaje=100 WHERE folio=?", (c["folio"],))
    db.commit()
    assert services.verificar(db, c["folio"], SECRETO)["valida"] is False


def test_RF_verificacion_folio_inexistente(db):
    assert services.verificar(db, "CCD-0000-AAAAAA", SECRETO) is None


def test_RNF_sello_distinto_con_otra_clave(db):
    c = _emitir(db)
    assert services.verificar(db, c["folio"], "otra-clave")["valida"] is False


# --- Flujo completo por la interfaz -----------------------------------------
def test_flujo_completo_por_roles(client):
    entrar(client, "promotor1@demo.test")
    r = client.post("/promotor/actividad/1", data={"accion": "constancia", "inscripcion_id": 1},
                    follow_redirects=True)
    folio = re.search(r"CCD-\d{4}-[0-9A-F]{6}", r.get_data(as_text=True)).group(0)
    client.post("/logout")

    entrar(client, "alumno1@demo.test")
    pdf = client.get(f"/constancia/{folio}.pdf")
    assert pdf.status_code == 200 and pdf.data.startswith(b"%PDF")
    client.post("/logout")

    # La verificación del QR es pública (sin iniciar sesión).
    pub = client.get(f"/verificar/{folio}")
    assert pub.status_code == 200 and "Constancia válida" in pub.get_data(as_text=True)


# --- Seguridad y acceso ------------------------------------------------------
def test_RNF_estudiante_no_entra_a_vista_de_promotor(client):
    entrar(client, "alumno1@demo.test")
    assert client.get("/promotor").status_code == 403


def test_RNF_promotor_no_ve_grupo_ajeno(client):
    entrar(client, "promotor2@demo.test")
    assert client.get("/promotor/actividad/1").status_code == 403


def test_RNF_pdf_ajeno_prohibido(client, db):
    c = _emitir(db)
    entrar(client, "alumno2@demo.test")  # otro estudiante
    assert client.get(f"/constancia/{c['folio']}.pdf").status_code == 403


def test_RNF_sin_sesion_redirige_a_login(client):
    assert client.get("/actividades").status_code == 302


def test_RNF_login_incorrecto(client):
    r = client.post("/login", data={"email": "alumno1@demo.test", "password": "mala"})
    assert "incorrectos" in r.get_data(as_text=True)


def test_RNF_csrf_bloquea_post_sin_token(app):
    app.config["TESTING_SIN_CSRF"] = False
    c = app.test_client()
    assert c.post("/login", data={"email": "a", "password": "b"}).status_code == 400
