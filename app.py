import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

# --- Config ---
DB_DIR = os.getenv("DB_DIR", os.path.join(os.getcwd(), "data"))
os.makedirs(DB_DIR, exist_ok=True)
UPLOAD_DIR = os.path.join(DB_DIR, "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

DB_PATH = os.path.join(DB_DIR, "acuarios.db")
DATABASE_URI = f"sqlite:///{DB_PATH}"

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret-change-me")
app.config["UPLOAD_FOLDER"] = UPLOAD_DIR
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024  # 4 MB

db = SQLAlchemy(app)

# --- Models ---
class Aquarium(db.Model):
    __tablename__ = "aquariums"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    created_at = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    image_path = db.Column(db.String(255), nullable=True)

    measurements = db.relationship("Measurement", backref="aquarium", cascade="all,delete-orphan", lazy=True)

class Measurement(db.Model):
    __tablename__ = "measurements"
    id = db.Column(db.Integer, primary_key=True)
    aquarium_id = db.Column(db.Integer, db.ForeignKey("aquariums.id"), nullable=False)
    date = db.Column(db.Date, nullable=False, default=datetime.utcnow)

    nitrate = db.Column(db.Float, nullable=True)    # NO3
    phosphate = db.Column(db.Float, nullable=True)  # PO4
    kh = db.Column(db.Float, nullable=True)         # dKH
    magnesium = db.Column(db.Integer, nullable=True)
    calcium = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# --- One-time init ---
with app.app_context():
    db.create_all()

# --- Routes ---
@app.route("/")
def home():
    aquariums = Aquarium.query.order_by(Aquarium.name.asc()).all()
    # Si no hay selección, coge el primero (si existe)
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

    def to_float(val):
        v = (val or "").replace(",", ".").strip()
        return float(v) if v else None

    def to_int(val):
        v = (val or "").strip()
        return int(v) if v else None

    nitrate = to_float(request.form.get("nitrate"))
    phosphate = to_float(request.form.get("phosphate"))
    kh = to_float(request.form.get("kh"))
    magnesium = to_int(request.form.get("magnesium"))
    calcium = to_int(request.form.get("calcium"))

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

# --- API para la gráfica ---
@app.route("/api/measurements/<int:aq_id>")
def api_measurements(aq_id):
    q = (
        Measurement.query
        .filter(Measurement.aquarium_id == aq_id)
        .order_by(Measurement.date.asc())
        .all()
    )
    data = []
    for r in q:
        data.append({
            "date": r.date.strftime("%Y-%m-%d"),
            "nitrate": r.nitrate,
            "phosphate": r.phosphate,
            "kh": r.kh,
            "magnesium": r.magnesium,
            "calcium": r.calcium,
        })
    return jsonify(data)

# --- Edición rápida de acuario (nombre y fecha) ---
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
