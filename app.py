from flask import Flask, jsonify, render_template, request

from config import Config
from extensions import db
# Importing the models registers their tables with SQLAlchemy metadata.
from models import Estatus, Municipio, Solicitud, Usuario


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    db.init_app(app)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/generar-turno", methods=["POST"])
    def generar_turno():
        datos = request.get_json(silent=True) or {}
        campos_requeridos = (
            "curp",
            "nombre",
            "primer_apellido",
            "segundo_apellido",
            "telefono_contacto",
            "correo",
            "municipio",
            "nivel_educativo",
            "asunto",
        )

        if any(not str(datos.get(campo, "")).strip() for campo in campos_requeridos):
            return jsonify({"mensaje": "Faltan datos del formulario."}), 400

        return jsonify({"mensaje": "Los datos se cargaron correctamente."})

    return app


app = create_app()

if __name__ == "__main__":
    app.run()
