"""
Accounts for Student Hub.

* Registration form validation with regular expressions (college admission form style)
* Passwords are salted and hashed with PBKDF2 (never stored in plain text)
* Student -> UndergraduateStudent / PostgraduateStudent (inheritance + method overriding)
* One private data folder per user
"""
import hashlib
import hmac
import os
import re
import sqlite3
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_ROOT = os.path.join(BASE_DIR, "user_data")
USERS_DB = os.path.join(BASE_DIR, "hub_users.db")

USERNAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{3,15}")
NAME_RE = re.compile(r"[A-Za-z][A-Za-z .'-]{1,49}")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
PHONE_RE = re.compile(r"(?:\+91[- ]?)?[6-9]\d{9}")
PASSWORD_RE = re.compile(r"(?=.*[A-Za-z])(?=.*\d).{8,}")      # 8+ chars with a letter and a digit
COURSES = ["CSE (Data Science)", "CSE", "Information Technology", "AI & Machine Learning",
           "Electronics & Telecom", "Mechanical", "Civil", "Other"]


# ======================= exceptions =======================
class AuthError(Exception):
    """Base class for account errors."""


class InvalidFieldError(AuthError):
    pass


class WeakPasswordError(InvalidFieldError):
    pass


class DuplicateUserError(AuthError):
    pass


class WrongCredentialsError(AuthError):
    pass


# ======================= OOP: student profiles =======================
class Student:
    """Base class. Age is encapsulated behind a validating property."""

    def __init__(self, name, age, course):
        self.name = name
        self.age = age
        self.course = course
        self.username = self.email = self.phone = ""

    @property
    def age(self):
        return self.__age

    @age.setter
    def age(self, value):
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise InvalidFieldError("Age must be a whole number") from None
        if not 15 <= value <= 60:
            raise InvalidFieldError("Age must be between 15 and 60")
        self.__age = value

    @property
    def level(self):
        return "Student"

    def display_info(self):
        return f"{self.name}, age {self.age}, {self.course}"


class UndergraduateStudent(Student):
    def __init__(self, name, age, course, semester):
        super().__init__(name, age, course)
        self.semester = semester

    @property
    def level(self):
        return "Undergraduate"

    def display_info(self):                              # polymorphism: overrides the base method
        return f"{super().display_info()} - semester {self.semester}"


class PostgraduateStudent(Student):
    def __init__(self, name, age, course, thesis_topic):
        super().__init__(name, age, course)
        self.thesis_topic = thesis_topic

    @property
    def level(self):
        return "Postgraduate"

    def display_info(self):
        return f"{super().display_info()} - thesis: {self.thesis_topic}"


# ======================= helpers =======================
def hash_password(password, salt=None):
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return salt.hex(), digest.hex()


def verify_password(password, salt_hex, hash_hex):
    _, digest = hash_password(password, bytes.fromhex(salt_hex))
    return hmac.compare_digest(digest, hash_hex)


def user_dir(username):
    path = os.path.join(USER_ROOT, username.lower())
    os.makedirs(path, exist_ok=True)
    return path


def validate_profile(form):
    """Validate the registration / profile form. Returns a cleaned dict or raises InvalidFieldError."""
    clean = {key: str(form.get(key, "")).strip() for key in
             ("full_name", "age", "email", "phone", "course", "level", "semester", "thesis_topic")}
    if not NAME_RE.fullmatch(clean["full_name"]):
        raise InvalidFieldError("Enter your full name (letters, spaces, . ' - only)")
    Student(clean["full_name"], clean["age"], clean["course"])          # validates age through the setter
    if not EMAIL_RE.fullmatch(clean["email"]):
        raise InvalidFieldError("Enter a valid email address")
    if not PHONE_RE.fullmatch(clean["phone"]):
        raise InvalidFieldError("Enter a valid 10-digit Indian mobile number")
    if not clean["course"]:
        raise InvalidFieldError("Choose your course")
    if clean["level"] not in ("UG", "PG"):
        raise InvalidFieldError("Choose Undergraduate or Postgraduate")
    if clean["level"] == "UG":
        if not clean["semester"].isdigit() or not 1 <= int(clean["semester"]) <= 8:
            raise InvalidFieldError("Semester must be between 1 and 8")
        clean["thesis_topic"] = ""
    else:
        if len(clean["thesis_topic"]) < 3:
            raise InvalidFieldError("Enter your thesis topic")
        clean["semester"] = ""
    return clean


def build_student(row):
    if row["level"] == "UG":
        student = UndergraduateStudent(row["full_name"], row["age"], row["course"], row["semester"])
    else:
        student = PostgraduateStudent(row["full_name"], row["age"], row["course"], row["thesis_topic"])
    student.username, student.email, student.phone = row["username"], row["email"], row["phone"]
    return student


# ======================= database =======================
class AuthDB:
    def __init__(self, path=USERS_DB):
        self.con = sqlite3.connect(path)
        self.con.row_factory = sqlite3.Row
        self.con.execute("""CREATE TABLE IF NOT EXISTS users(
            username TEXT PRIMARY KEY COLLATE NOCASE, salt TEXT NOT NULL, pw_hash TEXT NOT NULL,
            full_name TEXT, age INTEGER, email TEXT, phone TEXT, course TEXT, level TEXT,
            semester TEXT, thesis_topic TEXT, created TEXT)""")
        self.con.commit()

    @staticmethod
    def check_password_strength(password):
        if not PASSWORD_RE.fullmatch(password):
            raise WeakPasswordError("Password needs 8+ characters with at least one letter and one digit")

    def register(self, username, password, confirm, form):
        username = username.strip()
        if not USERNAME_RE.fullmatch(username):
            raise InvalidFieldError("Username: 4-16 characters, start with a letter, use letters/digits/_")
        self.check_password_strength(password)
        if password != confirm:
            raise InvalidFieldError("Passwords do not match")
        clean = validate_profile(form)
        salt, digest = hash_password(password)
        try:
            self.con.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                             (username, salt, digest, clean["full_name"], int(clean["age"]), clean["email"],
                              clean["phone"], clean["course"], clean["level"], clean["semester"],
                              clean["thesis_topic"], datetime.now().isoformat(timespec="seconds")))
            self.con.commit()
        except sqlite3.IntegrityError:
            raise DuplicateUserError(f"The username '{username}' is already taken") from None
        user_dir(username)
        return self.login(username, password)

    def login(self, username, password):
        row = self.con.execute("SELECT * FROM users WHERE username=?", (username.strip(),)).fetchone()
        if row is None or not verify_password(password, row["salt"], row["pw_hash"]):
            raise WrongCredentialsError("Wrong username or password")
        user_dir(row["username"])
        return build_student(row)

    def update_profile(self, username, form):
        clean = validate_profile(form)
        self.con.execute("""UPDATE users SET full_name=?, age=?, email=?, phone=?, course=?, level=?,
                            semester=?, thesis_topic=? WHERE username=?""",
                         (clean["full_name"], int(clean["age"]), clean["email"], clean["phone"], clean["course"],
                          clean["level"], clean["semester"], clean["thesis_topic"], username))
        self.con.commit()
        row = self.con.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        return build_student(row)

    def change_password(self, username, old, new, confirm):
        self.login(username, old)                        # raises WrongCredentialsError if old is wrong
        self.check_password_strength(new)
        if new != confirm:
            raise InvalidFieldError("New passwords do not match")
        salt, digest = hash_password(new)
        self.con.execute("UPDATE users SET salt=?, pw_hash=? WHERE username=?", (salt, digest, username))
        self.con.commit()
