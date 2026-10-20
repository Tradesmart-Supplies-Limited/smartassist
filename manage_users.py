# Copyright © 2026 Tradesmart Supplies Limited. All rights reserved. Developed by Maurille Khonde.
"""Add, remove or reset DocuLoop users. Double-click manage_users.bat to run it.

Passwords are typed without being shown and are saved scrambled in private\\users.json (never on GitHub).
"""
import getpass
import sys

from core import auth


def ask_password():
    while True:
        first = getpass.getpass(f"  Password (at least {auth.MIN_PASSWORD} characters, not shown): ")
        if first == getpass.getpass("  Type it again: "):
            return first
        print("  The two passwords are different. Try again.")


def show_users():
    users = auth.load_users()
    if users:
        print(f"\nUsers ({len(users)} of {auth.MAX_USERS}): " + ", ".join(sorted(users)))
    else:
        print("\nNo users yet: DocuLoop opens without a login. Add the users before sharing it on the network.")


def main():
    print("DocuLoop users")
    while True:
        show_users()
        print("\n  1  Add a user\n  2  Reset a password\n  3  Remove a user\n  4  Close")
        choice = input("Choose 1-4: ").strip()
        try:
            if choice == "1":
                name = input("  New user name (for example maurille): ")
                print(f"  Added '{auth.set_password(name, ask_password(), new_user=True)}'.")
            elif choice == "2":
                name = input("  User name: ")
                print(f"  New password saved for '{auth.set_password(name, ask_password())}'.")
            elif choice == "3":
                name = input("  User name to remove: ")
                if input(f"  Remove '{auth.clean_name(name)}'? Type yes: ").strip().lower() == "yes":
                    auth.remove_user(name)
                    print("  Removed.")
            elif choice == "4":
                return
        except auth.UserError as problem:
            print(f"  {problem}")


if __name__ == "__main__":
    if sys.argv[1:] == ["check"]:          # used by start_doculoop_network.bat
        sys.exit(0 if auth.login_required() else 1)
    main()
