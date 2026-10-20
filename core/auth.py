# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Who may use DocuLoop: user names and passwords, and the log of who made which PDFs.

No Streamlit here. Passwords are never stored as typed: each one is scrambled with PBKDF2-SHA256
(Python's own hashlib, nothing to install) and a random salt, so even someone who opens the users
file cannot read them. The users file and the log live in private\\ and output\\, both git-ignored.
"""
import csv
import hashlib
import hmac
import json
import os
import secrets
from datetime import datetime

PROJECT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
USERS_FILE = os.path.join(PROJECT, "private", "users.json")
LOG_FILE = os.path.join(PROJECT, "output", "generation_log.csv")

MAX_USERS = 4             # the manager and three colleagues (owner's decision, 2026-10-20)
MIN_PASSWORD = 8
ITERATIONS = 200_000      # how hard the scrambling is: slow for a guesser, still instant for a login


class UserError(ValueError):
    """A plain-language problem with a user name or password."""


def _scramble(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), ITERATIONS).hex()


def load_users(path=USERS_FILE):
    """The saved users as {name: {"salt": ..., "hash": ...}}; empty when there is no users file yet."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_users(users, path=USERS_FILE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2)


def login_required(path=USERS_FILE):
    """DocuLoop asks for a login as soon as at least one user exists."""
    return bool(load_users(path))


def clean_name(name):
    """User names are compared without spaces around them and without caring about capitals."""
    return (name or "").strip().lower()


def set_password(name, password, path=USERS_FILE, new_user=False):
    """Add a user (new_user=True) or give an existing user a new password."""
    name = clean_name(name)
    if not name or not name.replace(".", "").replace("_", "").replace("-", "").isalnum():
        raise UserError("Use letters and numbers for the user name (dots, - and _ are fine too).")
    if len(password or "") < MIN_PASSWORD:
        raise UserError(f"The password needs at least {MIN_PASSWORD} characters.")
    users = load_users(path)
    if new_user and name in users:
        raise UserError(f"There is already a user called '{name}'.")
    if not new_user and name not in users:
        raise UserError(f"There is no user called '{name}'.")
    if new_user and len(users) >= MAX_USERS:
        raise UserError(f"DocuLoop is set up for {MAX_USERS} users. Remove one before adding another.")
    salt = secrets.token_hex(16)
    users[name] = {"salt": salt, "hash": _scramble(password, salt)}
    save_users(users, path)
    return name


def remove_user(name, path=USERS_FILE):
    name = clean_name(name)
    users = load_users(path)
    if name not in users:
        raise UserError(f"There is no user called '{name}'.")
    del users[name]
    save_users(users, path)


def check_login(name, password, path=USERS_FILE):
    """The cleaned user name when name and password are right, otherwise None."""
    name = clean_name(name)
    user = load_users(path).get(name)
    if user is None:
        _scramble(password or "", secrets.token_hex(16))   # same time taken, so a wrong name is not given away
        return None
    if hmac.compare_digest(_scramble(password or "", user["salt"]), user["hash"]):
        return name
    return None


def log_generation(user, client_name, file_names, path=LOG_FILE):
    """Add one line to output\\generation_log.csv: when, who, which client and which PDFs were made."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    new_file = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["date and time", "user", "client", "number of PDFs", "files"])
        writer.writerow([datetime.now().isoformat(timespec="seconds"), user or "(no login)", client_name,
                         len(file_names), " ".join(file_names)])
