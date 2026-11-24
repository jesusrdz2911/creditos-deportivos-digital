# Créditos deportivos digital (prototipo)

Plataforma web para gestionar el crédito complementario deportivo: inscripción en línea, asistencia
por sesión, acreditación con mínimo configurable y constancia en PDF con folio, sello digital y QR
verificable. Prototipo escolar de la materia SCC-1007 con **datos 100 % simulados**.

## Roles
- **Estudiante:** ve actividades y cupos, se inscribe, consulta su avance y descarga su constancia.
- **Promotor:** pasa lista, ve el porcentaje de cada alumno y autoriza la constancia.
- **Servicios Escolares:** verifica constancias por folio o QR.
- **Público:** la página `/verificar/<folio>` confirma si una constancia es válida.

## Cómo correrlo
```bash
python -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env               # llena SELLO_SECRET y SECRET_KEY (en Windows: copy)
flask --app app init-db            # crea la base y carga datos simulados
flask --app app run
```
Abre http://localhost:5000. Cuentas de prueba (contraseña `demo1234`):
`alumno1@demo.test`, `promotor1@demo.test`, `escolares@demo.test`.

Para que el programa lea el `.env`, exporta las variables antes de correr (`export SELLO_SECRET=...`)
o usa un cargador como `python-dotenv`.

## Pruebas
```bash
python -m pytest -v
```

## Reglas de negocio implementadas
| Id | Regla |
|---|---|
| RN-01 | Un estudiante no se inscribe dos veces en la misma actividad |
| RN-02 | No se excede el cupo |
| RN-03 | La constancia solo se emite si el porcentaje alcanza el mínimo (configurable por actividad) |
| RN-04 | Solo el promotor de la actividad autoriza sus constancias |
| RN-05 | Una constancia no se emite dos veces |
| RN-06 | El mínimo de asistencia es un parámetro, no está fijo en el código |

## Alcance legal del sello
El sello (HMAC-SHA256 con una clave del servidor) detecta alteraciones y registra quién autorizó. **No equivale
a una firma electrónica avanzada.** Una implementación real tendría que integrar la e.firma o el mecanismo
que defina el TecNM.

## Estructura
```
app/            código (rutas, reglas, PDF, base de datos, plantillas)
tests/          pruebas automáticas
.env.example    variables necesarias (sin valores)
```
