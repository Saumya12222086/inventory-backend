from flask import Flask, request, jsonify
from flask_cors import CORS
from threading import Lock, Thread
from datetime import datetime, timedelta, UTC
import time

app = Flask(__name__)
CORS(app)

# ===== Repository Layer =====
inventory = {
    "SKU123": 5
}

reservations = {}   # reservation_id -> data
lock = Lock()

RESERVATION_TTL = timedelta(minutes=5)

# ===== Service Layer =====

def now_utc():
    return datetime.now(UTC)

# Auto cleanup thread (bonus but allowed)
def background_cleaner():
    while True:
        with lock:
            cleanup_expired()
        time.sleep(30)

def cleanup_expired():
    """Release abandoned carts automatically."""
    current = now_utc()
    for rid, r in list(reservations.items()):
        if r["status"] == "RESERVED" and r["expires_at"] < current:
            inventory[r["sku"]] += r["quantity"]
            r["status"] = "EXPIRED"

def reserve_logic(sku, qty, rid):
    cleanup_expired()

    # Idempotent
    if rid in reservations:
        return reservations[rid], 200

    stock = inventory.get(sku, 0)

    if stock < qty:
        return {"error": "Insufficient stock"}, 409

    # Temporary block
    inventory[sku] -= qty

    expires_at = now_utc() + RESERVATION_TTL
    reservation = {
        "reservation_id": rid,
        "sku": sku,
        "quantity": qty,
        "status": "RESERVED",
        "created_at": now_utc().isoformat(),
        "expires_at": expires_at,
        "expires_at_iso": expires_at.isoformat()
    }

    reservations[rid] = reservation
    return reservation, 200

def confirm_logic(rid):
    cleanup_expired()

    if isinstance(rid, dict):
        rid = rid.get("reservation_id")

    r = reservations.get(rid)
    if not r:
        return {"error": "Reservation not found"}, 404

    # Idempotent confirm
    if r["status"] == "CONFIRMED":
        return r, 200

    if r["status"] != "RESERVED":
        return {"error": "Reservation expired or cancelled"}, 409

    # Permanent deduction
    r["status"] = "CONFIRMED"
    return r, 200

def cancel_logic(rid):
    cleanup_expired()

    if isinstance(rid, dict):
        rid = rid.get("reservation_id")

    r = reservations.get(rid)
    if not r:
        return {"error": "Reservation not found"}, 404

    # Idempotent
    if r["status"] in ["CANCELLED", "EXPIRED"]:
        return r, 200

    # Release temporary block
    if r["status"] == "RESERVED":
        inventory[r["sku"]] += r["quantity"]

    r["status"] = "CANCELLED"
    return r, 200

# ===== Controller Layer =====

@app.route("/", methods=["GET"])
def health():
    return jsonify({
        "status": "Smart Inventory System Running",
        "time": now_utc().isoformat()
    })

@app.route("/inventory/<sku>", methods=["GET"])
def get_inventory(sku):
    with lock:
        cleanup_expired()
        return jsonify({
            "sku": sku,
            "available": inventory.get(sku, 0)
        })

@app.route("/inventory/reserve", methods=["POST"])
def reserve_controller():
    data = request.json

    sku = data.get("sku")
    qty = int(data.get("quantity", 0))
    rid = data.get("reservation_id")

    if not sku or not rid:
        return jsonify({"error": "sku and reservation_id required"}), 400

    with lock:
        result, code = reserve_logic(sku, qty, rid)
        return jsonify(result), code

@app.route("/checkout/confirm", methods=["POST"])
def confirm_controller():
    data = request.json
    rid = data.get("reservation_id")

    with lock:
        result, code = confirm_logic(rid)
        return jsonify(result), code

@app.route("/checkout/cancel", methods=["POST"])
def cancel_controller():
    data = request.json
    rid = data.get("reservation_id")

    with lock:
        result, code = cancel_logic(rid)
        return jsonify(result), code

# Start background cleaner
Thread(target=background_cleaner, daemon=True).start()

if __name__ == "__main__":
    app.run(debug=True)
