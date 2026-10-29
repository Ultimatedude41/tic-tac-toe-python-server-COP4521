
import hashlib
import hmac
import os
import sqlite3

ITERATIONS = 300_000


class AccountStore:
	def __init__(self, filename="accounts.db"):
		self.db = sqlite3.connect(filename)
		self.db.row_factory = sqlite3.Row
		self.db.execute("""
			CREATE TABLE IF NOT EXISTS accounts (
				username TEXT PRIMARY KEY COLLATE NOCASE,
				salt BLOB NOT NULL,
				password_hash BLOB NOT NULL,
				info TEXT NOT NULL DEFAULT ''
			)
		""")
		self.db.commit()

	@staticmethod
	def _hash_password(password, salt):
		return hashlib.pbkdf2_hmac(
			"sha256", password.encode("utf-8"), salt, ITERATIONS
		)

	def register(self, username, password):
		if not username or len(username) > 20:
			return False, "Username must contain 1-20 characters."
		if not all(c.isalnum() or c in "_-" for c in username):
			return False, "Username may contain letters, numbers, _ and - only."
		if not password or len(password) > 256:
			return False, "Password must contain 1-256 characters."

		salt = os.urandom(16)
		password_hash = self._hash_password(password, salt)

		try:
			self.db.execute(
				"INSERT INTO accounts (username, salt, password_hash) "
				"VALUES (?, ?, ?)",
				(username, salt, password_hash),
			)
			self.db.commit()
			return True, "Account registered successfully."
		except sqlite3.IntegrityError:
			return False, "That username is already registered."

	def authenticate(self, username, password):
		row = self.db.execute(
			"SELECT salt, password_hash FROM accounts WHERE username = ?",
			(username,),
		).fetchone()

		if row is None:
			return False

		candidate = self._hash_password(password, row["salt"])
		return hmac.compare_digest(candidate, row["password_hash"])

	def exists(self, username):
		return self.db.execute(
			"SELECT 1 FROM accounts WHERE username = ?", (username,)
		).fetchone() is not None

	def get_info(self, username):
		row = self.db.execute(
			"SELECT info FROM accounts WHERE username = ?", (username,)
		).fetchone()
		return None if row is None else row["info"]

	def set_info(self, username, info):
		cursor = self.db.execute(
			"UPDATE accounts SET info = ? WHERE username = ?",
			(info, username),
		)
		self.db.commit()
		return cursor.rowcount > 0

	def close(self):
		self.db.close()

