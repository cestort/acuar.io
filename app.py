import os
import re
from datetime import datetime, date as _date

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, jsonify, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text
from werkzeug.utils import secure_filename

# =========================================================
# Configuración de Base de Datos
# - Producción (Render): usar env var DATABASE_URL (Supabase Postgres)
#     ej: postgresql://postgres:PASS@HOST:5432/postgres?sslmode=require
# - Desarrollo: fallback a SQLite en ./data/acuarios.db
# =========================================================
DEFAULT_DB_DIR = os.path.join(os.getcwd(), "data")
os.makedirs(DEFAULT_DB_DIR, exist_ok=True)
SQLITE_PATH = os.path.join(DEFAULT_DB_DIR, "acuarios.db")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# En Render queremos que falle si no hay DATABASE_URL (para no caer a SQLite sin querer)
if os.getenv("RENDER") and not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL no definida en Render. Configúrala con tu cadena de Supabase."
    )

if DATABASE_URL:
    # Normaliza postgres:// -> postgresql:// si fuese necesario
    DATABASE_URI = DATABASE_URL.replace("postgres://", "postgresql://", 1)
else:
    DATABASE_URI = f"sqlite:///{SQLITE_PATH}"

# =========================================================
# Configuración de uploads (imágenes)
# - En Render Free el FS es efímero. Sirve para pruebas.
# =========================================================
DEFAULT_UPLOAD_BASE = os.path.join(DEFAULT_DB_DIR, "uploads")
UPLOAD_BASE = os.getenv("UPLOAD_DIR", DEFAULT_UPLOAD_BASE)
os.makedirs(UPLOAD_BASE, exist_ok=True)

# =========================================================
# App Flask
# =========================================================
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev")
app.config["UPLOAD_FOLDER"] = UPLOAD_BASE
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4 MB por imagen

db = SQLAlchemy(app)

# =========================================================
# Modelos
# =========================================================
class Aquarium(db.Model):
    __tablename__ = "aquariums"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    created_at = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    image_path = db.Column(db.String(255), nullable=True)
    measurements = db.relationship(
        "Measurement",
        backref="aquarium",
        cascade="all,delete-orphan",
        lazy=True
    )

class Measurement(db.Model):
    __tablename__ = "measurements"
    id = db.Column(db.Integer, primary_key=True)
    aquarium_id = db.Column(db.Integer, db.ForeignKey("aquariums.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)

    nitrate = db.Column(db.Float, nullable=True)     # NO3 (mg/L)
    phosphate = db.Column(db.Float, nullable=True)   # PO4 (mg/L)
    kh = db.Column(db.Float, nullable=True)          # dKH
    magnesium = db.Column(db.Integer, nullable=True) # ppm
    calcium = db.Column(db.Integer, nullable=True)   # ppm

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# Crear tablas (si no existen) con logs claros
with app.app_context():
    try:
        db.create_all()
        print("✅ Tablas creadas/verificadas correctamente.")
    except Exception as e:
        print(f"❌ Error al crear tablas: {e}")
        raise

# =========================================================
# Utilidades
# =========================================================
def _to_float(val: str | None):
    v = (val or "").replace(",", ".").strip()
    return float(v) if v else None

def _to_int(val: str | None):
    v = (val or "").strip()
    return int(v) if v else None

def _mask_url(url: str) -> str:
    return re.sub(r":([^:@/]+)@", r":******@", str(url))

# =========================================================
# Rutas
# =========================================================
@app.route("/")
def home():
    aquariums = Aquarium.query.order_by(Aquarium.name.asc()).all()
    selected_id = request.args.get("aquarium_id", type=int)
    if selected_id is None and aquariums:
        selected_id = aquariums[0].id
    return render_template("dashboard.html", aquariums=aquariums, selected_id=selected_id)

@app.route("/aquarium", methods=["POST"])
def create_aquarium():
    name = request.form.get("name", "").strip()
    created_at_str = request.form.get("created_at", "").strip()
    created_at = datetime.strptime(created_at_str, "%Y-%m-%d").date() if created_at_str else datetime.utcnow().date()

    if not name:
        flash("El nombre del acuario es obligatorio.", "danger")
        return redirect(url_for("home"))

    img = request.files.get("image")
    image_path = None
    if img and img.filename:
        filename = secure_filename(img.filename)
        save_as = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
        img.save(os.path.join(app.config["UPLOAD_FOLDER"], save_as))
        image_path = save_as

    try:
        aq = Aquarium(name=name, created_at=created_at, image_path=image_path)
        db.session.add(aq)
        db.session.commit()
        flash("Acuario creado.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error creando acuario: {e}", "danger")

    return redirect(url_for("home"))

@app.route("/aquarium/<int:aq_id>", methods=["POST"])
def update_aquarium(aq_id):
    aq = Aquarium.query.get_or_404(aq_id)
    name = request.form.get("name", "").strip()
    created_at_str = request.form.get("created_at", "").strip()
    created_at = datetime.strptime(created_at_str, "%Y-%m-%d").date() if created_at_str else aq.created_at

    img = request.files.get("image")
    if img and img.filename:
        filename = secure_filename(img.filename)
        save_as = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{filename}"
        img.save(os.path.join(app.config["UPLOAD_FOLDER"], save_as))
        aq.image_path = save_as

    if name:
        aq.name = name
    aq.created_at = created_at

    try:
        db.session.commit()
        flash("Acuario actualizado.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error actualizando: {e}", "danger")
    return redirect(url_for("home", aquarium_id=aq.id))

@app.route("/aquarium/<int:aq_id>/image")
def aquarium_image(aq_id):
    aq = Aquarium.query.get_or_404(aq_id)
    if not aq.image_path:
        return "", 404
    return send_from_directory(app.config["UPLOAD_FOLDER"], aq.image_path)

@app.route("/measurement", methods=["POST"])
def create_measurement():
    aquarium_id = request.form.get("aquarium_id", type=int)
    if not aquarium_id:
        flash("Selecciona un acuario.", "danger")
        return redirect(url_for("home"))

    date_str = request.form.get("date", "").strip()
    date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else datetime.utcnow().date()

    nitrate = _to_float(request.form.get("nitrate"))
    phosphate = _to_float(request.form.get("phosphate"))
    kh = _to_float(request.form.get("kh"))
    magnesium = _to_int(request.form.get("magnesium"))
    calcium = _to_int(request.form.get("calcium"))

    try:
        m = Measurement(
            aquarium_id=aquarium_id,
            date=date,
            nitrate=nitrate,
            phosphate=phosphate,
            kh=kh,
            magnesium=magnesium,
            calcium=calcium,
        )
        db.session.add(m)
        db.session.commit()
        flash("Registro guardado.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error guardando registro: {e}", "danger")

    return redirect(url_for("home", aquarium_id=aquarium_id))



@app.route("/api/measurements/<int:aq_id>")
def api_measurements(aq_id):
    try:
        # Verificar que el acuario existe
        aquarium = Aquarium.query.get(aq_id)
        if not aquarium:
            return jsonify({"error": "Aquarium not found"}), 404
            
        measurements = (
            Measurement.query
            .filter(Measurement.aquarium_id == aq_id)
            .order_by(Measurement.date.asc())
            .all()
        )
        
        data = []
        for measurement in measurements:
            # Manejo robusto de fechas
            date_str = None
            if measurement.date:
                if isinstance(measurement.date, (datetime, _date)):
                    date_str = measurement.date.strftime("%Y-%m-%d")
                else:
                    # Si por alguna razón está como string
                    try:
                        parsed_date = datetime.fromisoformat(str(measurement.date))
                        date_str = parsed_date.strftime("%Y-%m-%d")
                    except Exception:
                        # Si no se puede parsear, usar la fecha de creación como fallback
                        if measurement.created_at:
                            date_str = measurement.created_at.strftime("%Y-%m-%d")
            
            # Solo agregar registros con fecha válida
            if date_str:
                data.append({
                    "id": measurement.id,
                    "date": date_str,
                    "nitrate": measurement.nitrate,
                    "phosphate": measurement.phosphate,
                    "kh": measurement.kh,
                    "magnesium": measurement.magnesium,
                    "calcium": measurement.calcium,
                })
        
        return jsonify(data)
        
    except Exception as e:
        print(f"Error in api_measurements: {e}")
        return jsonify({"error": "Internal server error"}), 500
    

@app.route("/api/aquariums")
def api_aquariums():
    """Endpoint para obtener datos de todos los acuarios con sus imágenes"""
    try:
        aquariums = Aquarium.query.order_by(Aquarium.name.asc()).all()
        data = []
        for aq in aquariums:
            aquarium_data = {
                "id": aq.id,
                "name": aq.name,
                "created_at": aq.created_at.strftime("%Y-%m-%d") if aq.created_at else None,
                "image_url": url_for('aquarium_image', aq_id=aq.id) if aq.image_path else None,
                "has_image": bool(aq.image_path)
            }
            data.append(aquarium_data)
        return jsonify(data)
    except Exception as e:
        print(f"Error in api_aquariums: {e}")
        return jsonify({"error": "Internal server error"}), 500

# ---------------------------------------------------------
# Diagnóstico rápido de conexión (útil para verificar Supabase)
# ---------------------------------------------------------
@app.route("/_diag/db")
def diag_db():
    try:
        with db.engine.connect() as con:
            dbname = con.execute(text("select current_database()")).scalar()
            schema = con.execute(text("select current_schema()")).scalar()
            tables = [r[0] for r in con.execute(
                text("select tablename from pg_tables where schemaname=:s"),
                {"s": "public"}
            )]
        return jsonify({
            "engine_url": _mask_url(db.engine.url),
            "current_database": dbname,
            "current_schema": schema,
            "public_tables": tables
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# =========================================================
# Main
# =========================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
