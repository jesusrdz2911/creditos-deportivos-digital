CREATE TABLE IF NOT EXISTS usuario (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  rol TEXT NOT NULL CHECK (rol IN ('estudiante','promotor','escolares')),
  no_control TEXT
);
CREATE TABLE IF NOT EXISTS actividad (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  nombre TEXT NOT NULL,
  periodo TEXT NOT NULL,
  horario TEXT NOT NULL,
  cupo INTEGER NOT NULL CHECK (cupo > 0),
  sesiones_totales INTEGER NOT NULL CHECK (sesiones_totales > 0),
  minimo_pct INTEGER NOT NULL DEFAULT 80 CHECK (minimo_pct BETWEEN 1 AND 100),
  promotor_id INTEGER NOT NULL REFERENCES usuario(id)
);
CREATE TABLE IF NOT EXISTS inscripcion (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  estudiante_id INTEGER NOT NULL REFERENCES usuario(id),
  actividad_id INTEGER NOT NULL REFERENCES actividad(id),
  creada_en TEXT NOT NULL,
  UNIQUE (estudiante_id, actividad_id)
);
CREATE TABLE IF NOT EXISTS sesion (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  actividad_id INTEGER NOT NULL REFERENCES actividad(id),
  fecha TEXT NOT NULL,
  UNIQUE (actividad_id, fecha)
);
CREATE TABLE IF NOT EXISTS asistencia (
  sesion_id INTEGER NOT NULL REFERENCES sesion(id),
  estudiante_id INTEGER NOT NULL REFERENCES usuario(id),
  presente INTEGER NOT NULL CHECK (presente IN (0,1)),
  PRIMARY KEY (sesion_id, estudiante_id)
);
CREATE TABLE IF NOT EXISTS constancia (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  inscripcion_id INTEGER NOT NULL UNIQUE REFERENCES inscripcion(id),
  folio TEXT NOT NULL UNIQUE,
  porcentaje REAL NOT NULL,
  emitida_en TEXT NOT NULL,
  autorizada_por INTEGER NOT NULL REFERENCES usuario(id),
  sello TEXT NOT NULL
);
