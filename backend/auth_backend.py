from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import time, json, os, secrets, random, re, bcrypt, smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDIT_FOLDER = "audit_repo"
AUDIT_LOG = os.path.join(AUDIT_FOLDER, "audit_log.json")
MEMBERS_FILE = os.path.join(AUDIT_FOLDER, "members.json")
os.makedirs(AUDIT_FOLDER, exist_ok=True)

# ---------------- PASSWORD HELPERS ----------------
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

# ---------------- INITIAL MEMBERS ----------------
if not os.path.exists(MEMBERS_FILE):
    members = {
        "M001": {"password": hash_password("user"), "email": "user1@example.com", "lockout_until": 0, "attempts": 3},
        "M002": {"password": hash_password("user2"), "email": "user2@example.com", "lockout_until": 0, "attempts": 3},
        "M003": {"password": hash_password("user3"), "email": "user3@example.com", "lockout_until": 0, "attempts": 3},
    }
    with open(MEMBERS_FILE, "w") as f:
        json.dump(members, f, indent=2)

def load_members():
    with open(MEMBERS_FILE, "r") as f:
        return json.load(f)

def save_members(members):
    with open(MEMBERS_FILE, "w") as f:
        json.dump(members, f, indent=2)

# ---------------- EMAIL CONFIG ----------------
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

def send_transaction_email(recipient_email: str, transaction_id: str, amount: float, description: str):
    if not SMTP_USER or not SMTP_PASS:
        print("Email notification skipped: SMTP credentials are not configured.")
        return
    msg = MIMEMultipart()
    msg["From"] = SMTP_USER
    msg["To"] = recipient_email
    msg["Subject"] = "Transaction Confirmation"

    body = f"""
    Dear Member,

    Your transaction has been recorded successfully.
    Transaction ID: {transaction_id}
    Amount: {amount}
    Description: {description}

    Thank you,
    Audit Verification System
    """
    msg.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, recipient_email, msg.as_string())
    except Exception as e:
        print("Email sending failed:", e)

def get_member_email(member_id: str) -> str:
    members = load_members()
    member = members.get(member_id)
    if member:
        return member.get("email")
    return None

# ---------------- DATA MODELS ----------------
class LoginRequest(BaseModel):
    member_id: str
    password: str

class Transaction(BaseModel):
    transaction_id: str
    amount: float
    member_id: str
    description: str
    method: str = "manual"
    phone_number: str = None

class MobileMoneyRequest(BaseModel):
    member_id: str
    amount: float
    phone_number: str
    description: str
    network: str

class AddMemberRequest(BaseModel):
    member_id: str
    password: str
    email: str

class ModifyMemberRequest(BaseModel):
    new_member_id: str
    new_password: str

class ResetPasswordRequest(BaseModel):
    email: str
    new_password: str

class ForgotPasswordRequest(BaseModel):
    email: str

# ---------------- ADMIN 2FA ----------------
admin_codes = {}

class AdminVerifyRequest(BaseModel):
    member_id: str
    code: str

@app.post("/admin_login")
def admin_login(req: LoginRequest):
    if req.member_id == "admin" and req.password == "admin":
        code = str(secrets.randbelow(1000000)).zfill(6)
        admin_codes[req.member_id] = {"code": code, "expires": time.time() + 300}
        return {"step": "2fa_required", "message": "Enter the 2FA code", "code": code}
    else:
        raise HTTPException(status_code=401, detail="Invalid admin credentials")

@app.post("/admin_verify")
def admin_verify(req: AdminVerifyRequest):
    record = admin_codes.get(req.member_id)
    if not record:
        raise HTTPException(status_code=400, detail="No 2FA code generated")
    if time.time() > record["expires"]:
        raise HTTPException(status_code=400, detail="Code expired")
    if req.code != record["code"]:
        raise HTTPException(status_code=401, detail="Invalid code")
    del admin_codes[req.member_id]
    return {"success": True, "message": "Admin login successful"}
# ---------------- MEMBER LOGIN ----------------
@app.post("/member_login")
def member_login(req: LoginRequest):
    members = load_members()
    member = members.get(req.member_id)
    if not member:
        raise HTTPException(status_code=401, detail="Invalid Member ID")

    if time.time() < member["lockout_until"]:
        minutes_left = int((member["lockout_until"] - time.time()) / 60)
        raise HTTPException(status_code=403, detail=f"Account locked. Try again in {minutes_left} minutes.")

    if verify_password(req.password, member["password"]):
        member["attempts"] = 3
        save_members(members)
        return {"success": True, "message": "Login successful"}
    else:
        member["attempts"] -= 1
        if member["attempts"] <= 0:
            member["lockout_until"] = time.time() + 2 * 60 * 60
            member["attempts"] = 3
            save_members(members)
            raise HTTPException(status_code=403, detail="Too many failed attempts. Account locked for 2 hours.")
        save_members(members)
        raise HTTPException(status_code=401, detail=f"Invalid password. Attempts remaining: {member['attempts']}")

# ---------------- MEMBER MANAGEMENT ----------------
def is_strong_password(password: str) -> bool:
    return (
        len(password) >= 8 and
        re.search(r"[A-Z]", password) and
        re.search(r"[a-z]", password) and
        re.search(r"[0-9]", password) and
        re.search(r"[^A-Za-z0-9]", password)
    )

@app.post("/add_member")
def add_member(req: AddMemberRequest):
    if not is_strong_password(req.password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least 8 characters, including uppercase, lowercase, number, and special character."
        )

    members = load_members()
    if req.member_id in members:
        raise HTTPException(status_code=400, detail="Member ID already exists")
    members[req.member_id] = {
        "password": hash_password(req.password),
        "email": req.email,
        "lockout_until": 0,
        "attempts": 3
    }
    save_members(members)
    return {"success": True, "message": f"Member {req.member_id} added successfully"}

@app.post("/reset_password")
def reset_password(req: ResetPasswordRequest):
    members = load_members()
    for member_id, data in members.items():
        if data.get("email") == req.email:
            if not is_strong_password(req.new_password):
                raise HTTPException(status_code=400, detail="New password does not meet requirements")
            data["password"] = hash_password(req.new_password)
            save_members(members)
            return {"success": True, "message": f"Password reset for {member_id} successful"}
    raise HTTPException(status_code=404, detail="Email not found")

@app.post("/forgot_password")
def forgot_password(req: ForgotPasswordRequest):
    members = load_members()
    for member_id, data in members.items():
        if data.get("email") == req.email:
            return {"success": True, "message": f"Password reset link sent to {req.email} (simulation)."}
    raise HTTPException(status_code=404, detail="Email not found")

@app.get("/members")
def get_members():
    return load_members()

@app.delete("/delete_member/{member_id}")
def delete_member(member_id: str):
    members = load_members()
    if member_id not in members:
        raise HTTPException(status_code=404, detail="Member not found")
    del members[member_id]
    save_members(members)
    return {"success": True, "message": f"Member {member_id} deleted successfully"}

@app.put("/modify_member/{member_id}")
def modify_member(member_id: str, req: ModifyMemberRequest):
    members = load_members()
    if member_id not in members:
        raise HTTPException(status_code=404, detail="Member not found")
    del members[member_id]
    members[req.new_member_id] = {
        "password": hash_password(req.new_password),
        "lockout_until": 0,
        "attempts": 3
    }
    save_members(members)
    return {"success": True, "message": f"Member {member_id} modified to {req.new_member_id} successfully"}
# ---------------- TRANSACTIONS ----------------
@app.get("/transactions")
def get_transactions():
    try:
        with open(AUDIT_LOG, "r") as f:
            data = json.load(f)
        if not isinstance(data, list):
            data = []
    except Exception:
        data = []
    total_amount = sum(tx.get("amount", 0) for tx in data)
    return {"transactions": data, "total_amount_received": total_amount}

@app.post("/transactions")
def add_transaction(tx: Transaction):
    try:
        with open(AUDIT_LOG, "r") as f:
            try:
                data = json.load(f)
            except:
                data = []
    except FileNotFoundError:
        data = []

    new_tx = {
        "transaction_id": tx.transaction_id,
        "amount": tx.amount,
        "member_id": tx.member_id,
        "description": tx.description,
        "method": tx.method,
        "phone_number": tx.phone_number
    }
    data.append(new_tx)
    with open(AUDIT_LOG, "w") as f:
        json.dump(data, f, indent=2)

    # 🔑 Email integration
    recipient_email = get_member_email(tx.member_id)
    if recipient_email:
        send_transaction_email(recipient_email, tx.transaction_id, tx.amount, tx.description)

    return {"success": True, "message": "Transaction added successfully"}

# ---------------- MOBILE MONEY ----------------
@app.post("/record_mobile")
def record_mobile(req: MobileMoneyRequest):
    try:
        # Load existing transactions
        try:
            with open(AUDIT_LOG, "r") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = []

        # Generate a transaction ID
        tx_id = f"MM{int(time.time())}{random.randint(100,999)}"

        new_tx = {
            "transaction_id": tx_id,
            "amount": req.amount,
            "member_id": req.member_id,
            "description": req.description,
            "method": "mobile_money",
            "phone_number": req.phone_number,
            "network": req.network,
            "timestamp": datetime.now().isoformat()
        }

        data.append(new_tx)
        with open(AUDIT_LOG, "w") as f:
            json.dump(data, f, indent=2)

        # 🔑 Email integration
        recipient_email = get_member_email(req.member_id)
        if recipient_email:
            send_transaction_email(recipient_email, tx_id, req.amount, req.description)

        return {"success": True, "message": "Mobile money transaction recorded", "transaction": new_tx}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------- VERIFY TRANSACTION ----------------
@app.get("/verify/{transaction_id}")
def verify_transaction(transaction_id: str):
    try:
        with open(AUDIT_LOG, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No transactions found")

    if not isinstance(data, list):
        raise HTTPException(status_code=404, detail="Invalid transaction log format")

    for tx in data:
        if tx.get("transaction_id") == transaction_id:
            return {"success": True, "transaction": tx}

    raise HTTPException(status_code=404, detail="Transaction not found")
