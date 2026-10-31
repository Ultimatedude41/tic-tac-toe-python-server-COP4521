import hashlib
import hmac
import os
import sqlite3

#An iteration value to hash passwords.
ITERATIONS = 300_000


class AccountStore:
	def __init__(self, filename="accounts.db"):
		"""
		Connect to SQLite database.
		"""
		self.db = sqlite3.connect(filename)
		self.db.row_factory = sqlite3.Row
		self.db.execute("""
			CREATE TABLE IF NOT EXISTS accounts (
				username TEXT,
				password TEXT,
				info TEXT
			)
		""")
		self.db.commit()

	def register(self, username, password):
		#Make sure the username and password are between 1 and 20 characters.
		#Make sure they're leters, numbers, underscores, and hyphens only.
		if not username or len(username) > 20:
			return False, "Username must contain 1-20 characters."
		if not all(c.isalnum() or c in "_-" for c in username):
			return False, "Username may contain letters, numbers, _ and - only."
		if not password or len(password) > 20:
			return False, "Password must contain 1-20 characters."

		try:
			self.db.execute(
				"INSERT INTO accounts (username, password) "
				"VALUES (?, ?)",
				(username, password),
			)
			self.db.commit()
			return True, "Account registered successfully."
		except sqlite3.IntegrityError:
			return False, "That username is already registered."

	def authenticate(self, username, password):
		#Check if the username and password match.
		row = self.db.execute("SELECT password FROM accounts WHERE username = ?",(username,),).fetchone()

		if row is None:
			return False

		return password == row["password"]

	def exists(self, username):
		#Check if an account exists and receive a simple value rather than the full data.
		return self.db.execute("SELECT username FROM accounts WHERE username = ?", (username,)).fetchone() is not None

	def get_info(self, username):
		#Getter for the info.
		row = self.db.execute("SELECT info FROM accounts WHERE username = ?", (username,)).fetchone()
		return None if row is None else row["info"]

	def set_info(self, username, info):
		#Update the info for the specified account.
		cursor = self.db.execute("UPDATE accounts SET info = ? WHERE username = ?", (info, username),)
		self.db.commit()
		return cursor.rowcount > 0

	def close(self):
		self.db.close()

