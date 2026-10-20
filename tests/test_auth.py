# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Logins and the generation log, with invented users in a temporary folder."""
import csv
import json

import pytest

from core import auth


@pytest.fixture
def users_file(tmp_path):
    return str(tmp_path / "private" / "users.json")


def test_no_users_means_no_login(users_file):
    assert auth.login_required(users_file) is False


def test_add_user_and_sign_in(users_file):
    auth.set_password("  Alice ", "correct horse", users_file, new_user=True)
    assert auth.login_required(users_file)
    assert auth.check_login("alice", "correct horse", users_file) == "alice"
    assert auth.check_login("ALICE ", "correct horse", users_file) == "alice"     # capitals and spaces ignored
    assert auth.check_login("alice", "wrong password", users_file) is None
    assert auth.check_login("bob", "correct horse", users_file) is None
    assert auth.check_login("alice", None, users_file) is None


def test_password_is_never_stored_as_typed(users_file):
    auth.set_password("alice", "correct horse", users_file, new_user=True)
    with open(users_file, encoding="utf-8") as f:
        text = f.read()
    assert "correct horse" not in text
    assert set(json.loads(text)["alice"]) == {"salt", "hash"}


def test_same_password_gives_different_scrambles(users_file):
    auth.set_password("alice", "same password", users_file, new_user=True)
    auth.set_password("bob", "same password", users_file, new_user=True)
    users = auth.load_users(users_file)
    assert users["alice"]["hash"] != users["bob"]["hash"]


def test_reset_password(users_file):
    auth.set_password("alice", "first password", users_file, new_user=True)
    auth.set_password("alice", "second password", users_file)
    assert auth.check_login("alice", "first password", users_file) is None
    assert auth.check_login("alice", "second password", users_file) == "alice"


def test_short_password_and_bad_names_refused(users_file):
    with pytest.raises(auth.UserError):
        auth.set_password("alice", "short", users_file, new_user=True)
    with pytest.raises(auth.UserError):
        auth.set_password("", "long enough pw", users_file, new_user=True)
    with pytest.raises(auth.UserError):
        auth.set_password("a b", "long enough pw", users_file, new_user=True)
    with pytest.raises(auth.UserError):
        auth.set_password("nobody", "long enough pw", users_file)          # reset of a user who does not exist


def test_duplicate_and_fifth_user_refused(users_file):
    for name in ["u1", "u2", "u3", "u4"]:
        auth.set_password(name, "long enough pw", users_file, new_user=True)
    with pytest.raises(auth.UserError):
        auth.set_password("u1", "long enough pw", users_file, new_user=True)
    with pytest.raises(auth.UserError):
        auth.set_password("u5", "long enough pw", users_file, new_user=True)


def test_remove_user(users_file):
    auth.set_password("alice", "correct horse", users_file, new_user=True)
    auth.remove_user("Alice", users_file)
    assert auth.check_login("alice", "correct horse", users_file) is None
    assert auth.login_required(users_file) is False
    with pytest.raises(auth.UserError):
        auth.remove_user("alice", users_file)


def test_generation_log(tmp_path):
    log = str(tmp_path / "output" / "generation_log.csv")
    auth.log_generation("alice", "BMS", ["BMS_INV-001.pdf", "BMS_INV-002.pdf"], log)
    auth.log_generation(None, "GCK", ["GCK_INV-009.pdf"], log)
    with open(log, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    assert rows[0] == ["date and time", "user", "client", "number of PDFs", "files"]
    assert rows[1][1:] == ["alice", "BMS", "2", "BMS_INV-001.pdf BMS_INV-002.pdf"]
    assert rows[2][1:] == ["(no login)", "GCK", "1", "GCK_INV-009.pdf"]
