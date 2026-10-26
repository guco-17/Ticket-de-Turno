CREATE DATABASE ticket_turno CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE ticket_turno;

CREATE TABLE municipios (
  id            INT AUTO_INCREMENT PRIMARY KEY,
  nombre        VARCHAR(100) NOT NULL UNIQUE,
  ultimo_turno  INT NOT NULL DEFAULT 0,   -- contador interno por municipio
  activo        TINYINT(1) NOT NULL DEFAULT 1
);

INSERT INTO municipios (nombre) VALUES
  ('Acuña'),
  ('Arteaga'),
  ('Monclova'),
  ('Parras'),
  ('Ramos Arizpe'),
  ('Saltillo'),
  ('Torreón');

CREATE TABLE estatus (
  id      INT AUTO_INCREMENT PRIMARY KEY,
  nombre  VARCHAR(30) NOT NULL UNIQUE
);

CREATE TABLE usuarios (
  id             INT AUTO_INCREMENT PRIMARY KEY,
  usuario        VARCHAR(50)  NOT NULL UNIQUE,
  password_hash  VARCHAR(255) NOT NULL,   -- bcrypt/argon2, nunca texto plano
  nombre         VARCHAR(100) NOT NULL,
  activo         TINYINT(1) NOT NULL DEFAULT 1,
  creado_en      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE solicitudes (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  municipio_id     INT NOT NULL,
  turno            INT NOT NULL,
  curp             CHAR(18) NOT NULL,
  nombre           VARCHAR(100) NOT NULL,
  apellido_paterno VARCHAR(100) NOT NULL,
  apellido_materno VARCHAR(100),
  fecha_nacimiento DATE,
  telefono         VARCHAR(15),
  correo           VARCHAR(120),
  nivel_educativo  VARCHAR(30) NOT NULL DEFAULT '',
  asunto           VARCHAR(50) NOT NULL DEFAULT '',
  estatus_id       INT NOT NULL DEFAULT 1,
  creado_en        DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  actualizado_en   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  CONSTRAINT fk_sol_mun  FOREIGN KEY (municipio_id) REFERENCES municipios(id),
  CONSTRAINT fk_sol_est  FOREIGN KEY (estatus_id)   REFERENCES estatus(id),
  CONSTRAINT uq_turno_municipio UNIQUE (municipio_id, turno),
  CONSTRAINT uq_curp UNIQUE (curp),
  INDEX idx_nombre (nombre, apellido_paterno)
);

INSERT INTO estatus (id, nombre) VALUES (1,'Pendiente'), (2,'Resuelto');