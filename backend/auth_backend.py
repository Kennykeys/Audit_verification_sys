from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

try:
    from backend.integrity import compute_transaction_hash, verify_transaction_hash
except ModuleNotFoundError:
    from integrity import compute_transaction_hash, verify_transaction_hash
try:
    from backend.config import Settings
    from backend.repository import AuditLedgerRepository, DuplicateTransactionError, LedgerCorruptionError
except ModuleNotFoundError:
    from config import Settings
    from repository import AuditLedgerRepository, DuplicateTransactionError, LedgerCorruptionError
import time, json, os, secrets, random, re, bcrypt, smtplib
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

legacy_settings = Settings.from_environment()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(legacy_settings.allowed_origins),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

AUDIT_FOLDER = "audit_repo"
AUDIT_LOG = str(Settings.from_environment().ledger_path)


def get_audit_repository():
    return AuditLedgerRepository(AUDIT_LOG)
MEMBERS_FILE = os.path.join(AUDIT_FOLDER, "members.json")
os.makedirs(AUDIT_FOLDER, exist_ok=True)

def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))

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


# ---------------- EMAIL CONFIGURATION ----------------
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")

def send_transaction_email(recipient_email: str, transaction_id: str, amount: float, description: str):
    if not SMTP_USER or not SMTP_PASS:
        print("Email notification skipped: SMTP credentials are not configured.")
        return
    message = MIMEMultipart()
    message["From"] = SMTP_USER
    message["To"] = recipient_email
    message["Subject"] = "Transaction Confirmation"
    body = (
        "Dear Member,\n\n"
        "Your transaction has been recorded successfully.\n"
        f"Transaction ID: {transaction_id}\n"
        f"Amount: {amount}\n"
        f"Description: {description}\n\n"
        "Audit Verification System"
    )
    message.attach(MIMEText(body, "plain"))
    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, recipient_email, message.as_string())
    except Exception as error:
        print(f"Email notification failed: {error}")

def get_member_email(member_id: str):
    members = load_members()
    member = members.get(member_id)
    if member:
        return member.get("email")
    return None



def send_account_modification_email(recipient_email: str, old_member_id: str, new_member_id: str):
    if not recipient_email or not SMTP_USER or not SMTP_PASS:
        print("Account modification email skipped: SMTP credentials are not configured.")
        return False

    message = MIMEMultipart()
    message["From"] = SMTP_USER
    message["To"] = recipient_email
    message["Subject"] = "Account Modification Alert"
    body = (
        "Dear Member,\n\n"
        "Your SACCO account details were modified by an administrator.\n\n"
        f"Old Member ID: {old_member_id}\n"
        f"New Member ID: {new_member_id}\n"
        "Password: hidden for security\n\n"
        "If you did not request this change, contact SACCO support immediately.\n\n"
        "Audit Verification System"
    )
    message.attach(MIMEText(body, "plain"))

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, recipient_email, message.as_string())
        return True
    except Exception as error:
        print(f"Account modification email failed: {error}")
        return False


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

# Legacy administrator authentication removed. Use backend.main /auth endpoints.

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

    if req.new_member_id != member_id and req.new_member_id in members:
        raise HTTPException(status_code=409, detail="New Member ID already exists")

    if not is_strong_password(req.new_password):
        raise HTTPException(status_code=400, detail="New password does not meet requirements")

    existing_member = members[member_id]
    member_email = existing_member.get("email")

    updated_member = {
        "password": hash_password(req.new_password),
        "email": member_email,
        "lockout_until": existing_member.get("lockout_until", 0),
        "attempts": existing_member.get("attempts", 3)
    }

    if req.new_member_id != member_id:
        del members[member_id]

    members[req.new_member_id] = updated_member
    save_members(members)

    email_sent = send_account_modification_email(
        member_email,
        member_id,
        req.new_member_id
    )

    return {
        "success": True,
        "message": f"Member {member_id} modified to {req.new_member_id} successfully",
        "email_alert_sent": email_sent
    }

# ---------------- TRANSACTIONS ----------------
@app.get("/transactions")
def get_transactions():
    try:
        return {"transactions": get_audit_repository().load_entries()}
    except LedgerCorruptionError as error:
        raise HTTPException(status_code=500, detail="Audit ledger integrity validation failed") from error


@app.post("/transactions")
def add_transaction(tx: Transaction):
    new_tx = {
        "transaction_id": tx.transaction_id,
        "amount": tx.amount,
        "member_id": tx.member_id,
        "description": tx.description,
        "date_time": datetime.now().isoformat(),
        "method": tx.method,
        "network": None,
        "phone_number": None,
    }
    new_tx["hash"] = compute_transaction_hash(new_tx)
    try:
        persisted_transaction = get_audit_repository().append_entry(new_tx)
    except DuplicateTransactionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except LedgerCorruptionError as error:
        raise HTTPException(status_code=409, detail="Ledger integrity verification failed") from error
    recipient_email = get_member_email(tx.member_id)
    if recipient_email:
        send_transaction_email(recipient_email, tx.transaction_id, tx.amount, tx.description)
    return {"success": True, "transaction": persisted_transaction}


@app.get("/verify/{transaction_id}")
def verify_transaction(transaction_id: str):
    try:
        data = get_audit_repository().load_entries()
    except LedgerCorruptionError:
        return {"transaction_id": transaction_id, "verified": False, "status": "tampered"}
    transaction = next((record for record in data if record.get("transaction_id") == transaction_id), None)
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    verified = verify_transaction_hash(transaction) or bool(transaction.get("entry_hash"))
    return {"transaction_id": transaction_id, "verified": verified, "status": "verified" if verified else "tampered"}


# ---------------- MOBILE MONEY (SIMULATION) ----------------
@app.post("/mobile_money")
def simulate_mobile_money(req: MobileMoneyRequest):
    success = random.choice([True, True, False])
    if not success:
        raise HTTPException(status_code=402, detail=f"{req.network} payment failed (simulation).")
    transaction_id = f"MM-{time.time_ns()}"
    new_tx = {
        "transaction_id": transaction_id,
        "amount": req.amount,
        "member_id": req.member_id,
        "description": req.description,
        "date_time": datetime.now().isoformat(),
        "method": "mobile_money",
        "network": req.network,
        "phone_number": req.phone_number,
    }
    new_tx["hash"] = compute_transaction_hash(new_tx)
    try:
        persisted_transaction = get_audit_repository().append_entry(new_tx)
    except DuplicateTransactionError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    except LedgerCorruptionError as error:
        raise HTTPException(status_code=409, detail="Ledger integrity verification failed") from error
    recipient_email = get_member_email(req.member_id)
    if recipient_email:
        send_transaction_email(recipient_email, transaction_id, req.amount, req.description)
    return {"success": True, "transaction": persisted_transaction}
