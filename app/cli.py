"""
Extra command-line commands, run with `flask --app app <command>`.

    python -m flask --app app hash-password   -> prints an ADMIN_PASSWORD_HASH value
"""
import getpass

import click
from werkzeug.security import generate_password_hash


def register_cli(app):
    @app.cli.command("hash-password")
    def hash_password():
        """Ask for an admin password and print its hash for your .env file."""
        password = getpass.getpass("New admin password: ")
        if len(password) < 10:
            raise click.ClickException("Use at least 10 characters.")
        if password != getpass.getpass("Repeat it: "):
            raise click.ClickException("Passwords did not match.")
        hashed = generate_password_hash(password)  # scrypt with a random salt
        # The hash contains "$" signs. Single quotes stop docker compose and
        # shells from treating them as variables.
        click.echo("\nAdd this line to your .env file:\n")
        click.echo(f"ADMIN_PASSWORD_HASH='{hashed}'")
