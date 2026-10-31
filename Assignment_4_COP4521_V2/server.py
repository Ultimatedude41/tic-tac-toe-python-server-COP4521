import argparse
import re
import select
import socket
import sys

from accounts import AccountStore
from games import Game


#A class Client should store the connection and session information for clients.
class Client:
	
	"""
	Initilaize the socket used to communicate, the address of the client,
	the incoming data until a command is received, outgoing messages,
	the username of a logged in client, whether the client is a guest or not,
	info about the guest, whether the client is logged in, the name
	dor authentication, and the number of unsuccessful log in attempts.
	"""
	def __init__(self, sock, address):
		self.sock = sock
		self.address = address
		self.input = bytearray()
		self.output = bytearray()
		self.username = None
		self.guest = False
		self.guest_info = ""
		self.state = "login"
		self.login_name = None
		self.login_failures = 0

class TicTacToeServer:
	def __init__(self, host, port, database):
		"""
		Initialize the network service and TCP port used by the client.
		Load the account database and provide account operations.	
		Initialize a listener socket that accepts connections.
		Map connected sockets to their Client objects.
		Map lowercase usernames to currently logged in clients.
		Store the currently active games.
		Store the active game invitations.
		Set a counter for unique guest usernames.
		Control whether the server continues running.
		"""
		self.host = host
		self.port = port
		self.accounts = AccountStore(database)
		self.listener = None
		self.clients = {}
		self.online = {}
		self.games = []
		self.invitations = {}
		self.next_guest = 1
		self.running = True

	@staticmethod
	def key(username):
		#Make username comparisons case-insensitive.
		return username.casefold()

	def send(self, client, message):
		#If a client exists, add the message to the client's output.
		#Make sure the line ending is compatible with Telnet.
		if client is None:
			return
		try:
			client.output.extend((str(message) + "\r\n").encode("utf-8"))
		except (ValueError, UnicodeError, TypeError):
			self.disconnect(client)

	def prompt(self, client):
		#Prompt the user for a username and password.
		if client.state == "login":
			self.send(client, "Login: enter a username or type guest")
		elif client.state == "password":
			self.send(client, "Password:")
		elif client.username:
			self.send(client, f"[{client.username}] Enter command (help for help):")

	def show_menu(self, client):
                        self.send(
                                client,
                                "**********COMMAND MENU**********\n" 
                                "who - List all online users\n"
                                "status [user] - Display a user's information\n"
                                "shout <message> - Broadcast a message to all online clients\n"
                                "tell <user> <message> - Tell a specific user a message\n"
                                "info [Info text] - change or show your information text\n"
                                "quit - logout\n"
                                "exit - logout\n"
                                "match <user> <b|w> - invite a user to a match\n"
                                "[A-C][1-3] - make a move in a tic-tac-to game\n"
                                "games - list the active games\n"
                                "help - print this menu\n"
                                "register <user> <passwd> - register a new user\n"
				"*********************************\n"
                        )


	def broadcast(self, message, exclude=None):
		#Send a message to every online client.
		for client in list(self.online.values()):
			if client is not exclude:
				self.send(client, message)

	def get_online(self, username):
		#Getter for the connected client associated with a username.
		return self.online.get(self.key(username))

	def player_game(self, username):
		#Search the active games and return games with active players. return None otherwise.
		username_key = self.key(username)
		for game in self.games:
			for player in game.players.values():
				if self.key(player) == username_key:
					return game
		return None

	def remove_invitations(self, username):
		#Remove invitation received  by a client.
		username_key = self.key(username)
		self.invitations.pop(username_key, None)

		#Remove invitations from a client who has logged out.
		for target, invitation in list(self.invitations.items()):
			inviter, _ = invitation
			if self.key(inviter) == username_key:
				self.invitations.pop(target, None)

	def end_player_game(self, username, message):
		#End game when a client disconnects.
		#Notify the opponent that the game has ended.
		game = self.player_game(username)
		if game is None:
			return

		for player in game.players.values():
			if self.key(player) != self.key(username):
				self.send(self.get_online(player), message)

		if game in self.games:
			self.games.remove(game)

	def disconnect(self, client):
		"""
		Remove client from a server, update the onloine clients,
		Remove their invitations, end their active games, and close
		the client's network socket.
		"""
		sock = client.sock
		if sock not in self.clients:
			return

		username = client.username

		if username:
			self.online.pop(self.key(username), None)
			self.remove_invitations(username)
			self.end_player_game(username, f"{username} disconnected. The game has ended.")
			self.broadcast(f"{username} has logged out.")

		self.clients.pop(sock, None)

		try:
			sock.close()
		except OSError:
			pass

	def logout(self, client):
		#Log the client out without closing their TCP connection.
		#Reset their session so another user may log in.
		username = client.username

		if username:
			self.online.pop(self.key(username), None)
			self.remove_invitations(username)
			self.end_player_game(username, f"{username} logged out. The game has ended.")
			self.broadcast(f"{username} has logged out.")

		client.username = None
		client.guest = False
		client.guest_info = ""
		client.state = "login"
		client.login_name = None
		client.login_failures = 0
		self.prompt(client)

	def login_guest(self, client):
		#Generate a unique guest username.
		#And add the guest to the online user list while announcing their arrival.
		while True:
			username = f"guest{self.next_guest}"
			self.next_guest += 1

			if (self.key(username) not in self.online and not self.accounts.exists(username)):
				break

		client.username = username
		client.guest = True
		client.state = "ready"
		self.online[self.key(username)] = client

		self.send(client, f"Logged in as {username} (guest).")
		self.broadcast(f"{username} has joined the server.", exclude=client)
		self.show_menu(client)
		self.prompt(client)


	def login_regular(self, client, username, password):
		"""
		Authenticate a registered user against the account database.
		Prevent duplicate logins and disconnect users after 3
		unsuccessful password attemps.
		"""
		if not self.accounts.authenticate(username, password):
			client.login_failures += 1
			self.send(client,"Login error: username/password do not match.")

			if client.login_failures >= 3:
				self.send(client, "Too many failed attempts; disconnecting.")
				self.disconnect(client)
				return

			client.state = "login"
			client.login_name = None
			self.prompt(client)
			return

		username_key = self.key(username)

		if username_key in self.online:
			self.send(client, "That account is already online.")
			client.state = "login"
			client.login_name = None
			self.prompt(client)
			return

		client.username = username
		client.guest = False
		client.state = "ready"
		self.online[username_key] = client

		self.send(client, f"Welcome, {username}.")
		self.broadcast(f"{username} has joined the server.", exclude=client)
		self.show_menu(client)
		self.prompt(client)

	def handle_login(self, client, line):
		"""
		Process usernames and passwords.
		Handles both Guest and registered accounts.
		"""
		if client.state == "login":
			username = line.strip()

			if not username:
				self.send(client, "Please enter a username or guest.")
				self.prompt(client)
				return

			if username.casefold() == "guest":
				self.login_guest(client)
				return

			client.login_name = username
			client.state = "password"
			self.send(client, "Password:")
			return

		if client.state == "password":
			self.login_regular(client, client.login_name or "", line)

	def command(self, client, line):
		"""
		Process the commands entered by clients.
		Supported commands are as follows:
		who - List all online users
		status [user] - Display a user's information
		shout <message> - Broadcast a message to all online clients.
		tell <user> <message> - Tell a specific user a message
		info [Info text] - change or show your information text.
		quit - logout
		exit - logout
		match <user> <b|w> - invite a user to a match
		[A-C][1-3] - make a move in a tic-tac-to game
		games - list the active games
		help - print this menu
		register <user> <passwd> - register a new user.
		"""
		line = line.strip()

		if not line:
			self.prompt(client)
			return

		if len(line) > 2048:
			self.send(client, "Error: command is too long.")
			self.prompt(client)
			return

		parts = line.split(maxsplit=2)
		cmd = parts[0].casefold()
		args = parts[1:]

		#If the client enters help, print the command list.
		if cmd == "help":
			self.show_menu(client)

		#If the client inputs quit or exit, log them out.
		elif cmd in ("quit", "exit"):
			self.logout(client)
			return

		#Display the online clients when a client enter who.
		elif cmd == "who":
			self.send(client, "Online users:")

			if not self.online:
				self.send(client, "No users are online.")
			else:
				for username in sorted(
					(c.username for c in self.online.values()),
					key=str.casefold
				):
					online_client = self.get_online(username)
					account_type = ("guest" if online_client.guest else "registered")
					playing = (" (playing)" if self.player_game(username) else "")
					self.send(client, f"  {username} [{account_type}]{playing}")

		#Check the atatus of the client or another client.
		#This includes whether they're online or not, whether they are in a game
		#, and their information.
		elif cmd == "status":
			if len(args) > 1:
				self.send(client, "Usage: status [user]")
			else:
				username = args[0] if args else client.username
				target = self.get_online(username)

			if target and target.guest:
				info = target.guest_info
				exists = True
			else:
				exists = self.accounts.exists(username)
				info = self.accounts.get_info(username) if exists else None

				if not exists:
					self.send(client, f"User does not exist: {username}")
				else:
					state = "online" if target else "offline"

					if target and target.guest:
						state += ", guest"

					if target and self.player_game(username):
						state += ", playing"

					self.send(client, f"{username}: {state}")
					self.send(client, f"Info: {info or '(none)'}")

		#Send a message to all online clients.
		elif cmd == "shout":
			message = line[len(parts[0]):].strip()

			if not message:
				self.send(client, "Usage: shout <message>")
			else:
				self.broadcast(f"[shout] {client.username}: {message}")

		#Send a private message to a specified online client.
		elif cmd == "tell":
			fields = line.split(maxsplit=2)

			if len(fields) != 3 or not fields[2].strip():
				self.send(client, "Usage: tell <user> <message>")
			else:
				username, message = fields[1], fields[2]
				target = self.get_online(username)

				if not self.accounts.exists(username) and target is None:
					self.send(client, f"User does not exist: {username}")
				elif target is None:
					self.send(client, f"User is not online: {username}")
				else:
					self.send(target, f"[tell] {client.username}: {message}")
					self.send(client, f"Message sent to {target.username}.")

		#Change the client info to what the client writes. Save up to 100 characters.
		#Save this info to an account if the client is logged in.
		elif cmd == "info":
			info = line[len(parts[0]):].strip()

			if not info:
				if client.guest:
					current = client.guest_info
				else:
					current = self.accounts.get_info(client.username)

				self.send(client, f"Info: {current or '(none)'}")

			elif len(info) > 100:
				self.send(client, "Info must be at most 100 characters.")

			elif client.guest:
				client.guest_info = info
				self.send(client, "Guest information updated for this session.")

			else:
				self.accounts.set_info(client.username, info)
				self.send(client, "Information updated.")

		#Allow the client to register an account.
		elif cmd == "register":
			fields = line.split(maxsplit=2)

			if len(fields) != 3:
				self.send(client, "Usage: register <user> <passwd>")
			else:
				_, username, password = fields
				_, message = self.accounts.register(username, password)
				self.send(client, message)

		#Validate a match invite and send the invitation to another client.
		elif cmd == "match":
			fields = line.split()

			if (len(fields) != 3 or fields[2].casefold() not in ("b", "w")):
				self.send(client, "Usage: match <user> <b|w>")
			else:
				self.invite(client, fields[1], fields[2].casefold())

		#Allow clients to accept invitations.
		elif cmd == "accept":
			if len(args) != 1:
				self.send(client, "Usage: accept <user>")
			else:
				self.accept_invite(client, args[0])

		#Allow clients to decline invitations.
		elif cmd == "decline":
			if len(args) != 1:
				self.send(client, "Usage: decline <user>")
			else:
				self.decline_invite(client, args[0])

		#Show the client all games that are in progress. Or alert them if there are no
		#games in progress.
		elif cmd == "games":
			if not self.games:
				self.send(client, "No games are in progress.")
			else:
				for number, game in enumerate(self.games, 1):
					self.send(client, f"Game {number}: X={game.players['X']}, O={game.players['O']}, turn={game.turn}, state={'finished' if game.is_finished() else 'active'}")

		#Process a move if the input matches a valid board coordinate.
		elif re.fullmatch(r"[A-Ca-c][1-3]", line):
			game = self.player_game(client.username)

			if not game:
				self.send(client, "You are not currently in a game.")
			else:
				ok, message = game.move(client.username, line)
				self.send(client, message)

				if ok:
					self.notify_game(game)

					if game.is_finished():
						result = (f"{game.winner} wins!" if game.winner else "The game is a draw.")
						self.send_game_players(game, result)
						self.games.remove(game)

		else:
			self.send(client, f"Unsupported command: {parts[0]}")

		self.prompt(client)

	def invite(self, client, target_name, color):
		#Send a game invitation to another client.
		#Check that neither play is playing or has another pending invite.
		target = self.get_online(target_name)

		if target is None and not self.accounts.exists(target_name):
			self.send(client, f"User does not exist: {target_name}")
			return

		if target is None:
			self.send(client, f"User is not online: {target_name}")
			return

		if target is client:
			self.send(client, "You cannot invite yourself.")
			return

		if (self.player_game(client.username) or self.player_game(target.username)):
			self.send(client, "One of the players is already in a game.")
			return

		sender_key = self.key(client.username)
		target_key = self.key(target.username)

		if target_key in self.invitations:
			self.send(client, "That user already has a pending invitation.")
			return

		if any(self.key(sender) == sender_key for sender, _ in self.invitations.values()):
			self.send(client, "You already have a pending invitation.")
			return

		self.invitations[target_key] = (client.username, color)

		self.send(target, f"{client.username} invites you to play. Use 'accept {client.username}' or 'decline {client.username}'.")
		self.send(client, f"Invitation sent to {target.username}.")

	def accept_invite(self, client, inviter_name):
		#Validate and accept an invitation.
		#Create a new game object and assign the players' colors.
		target_key = self.key(client.username)
		invitation = self.invitations.get(target_key)

		if (invitation is None or self.key(invitation[0]) != self.key(inviter_name)):
			self.send(client, "No matching invitation was found.")
			return

		inviter = self.get_online(invitation[0])

		if inviter is None:
			self.invitations.pop(target_key, None)
			self.send(client, "The inviting user is no longer online.")
			return

		if (self.player_game(client.username) or self.player_game(inviter.username)):
			self.invitations.pop(target_key, None)
			self.send(client, "One of the players is already in a game.")
			return

		color = invitation[1]
		self.invitations.pop(target_key, None)

		if color == "b":
			game = Game(inviter.username, client.username)
		else:
			game = Game(client.username, inviter.username)

		self.games.append(game)

		self.send_game_players(game, f"Game started! X (black): {game.players['X']}; O (white): {game.players['O']}.")
		self.notify_game(game)


	def decline_invite(self, client, inviter_name):
		#Remove pending invitation and notify the inviting player.
		target_key = self.key(client.username)
		invitation = self.invitations.get(target_key)

		if (invitation is None or self.key(invitation[0]) != self.key(inviter_name)):
			self.send(client, "No matching invitation was found.")
			return

		self.invitations.pop(target_key, None)
		inviter = self.get_online(invitation[0])

		self.send(client, "Invitation declined.")

		if inviter:
			self.send(inviter, f"{client.username} declined your invitation.")

	def send_game_players(self, game, message):
		#Send a message to both players participating in the game.
		for username in set(game.players.values()):
			self.send(self.get_online(username), message)

	def notify_game(self, game):
		#Send the updated board to both players.
		#Announce who's turn it is if the game is still active.
		self.send_game_players(game, game.render())

		if not game.is_finished():
			current = game.players[game.turn]
			self.send_game_players(game, f"Next turn: {current} ({game.turn}).")

	def process_line(self, client, raw):
		#Decode incoming bytes into UTF-8 text.
		#Route the input to login handling or command processing.
		#Catch invalid input and unexpected errors.
		try:
			line = raw.decode("utf-8").strip()
		except UnicodeDecodeError:
			self.send(client, "Error: input must be UTF-8 text.")
			return

		try:
			if client.state in ("login", "password"):
				self.handle_login(client, line)
			else:
				self.command(client, line)

		except (ValueError, KeyError, IndexError) as exc:
			print(f"Input error from {client.address}: {exc}")
			self.send(client, "Error: invalid command or arguments.")
			self.prompt(client)

		except Exception as exc:
			print(f"Command error from {client.address}: {exc!r}")
			self.send(client, "Error: command could not be completed.")
			self.prompt(client)

	def accept_connection(self):
		#Accept new incoming TCP connections.
		#Create Client object and initialize the login prompt.
		try:
			sock, address = self.listener.accept()
			sock.setblocking(False)

			client = Client(sock, address)
			self.clients[sock] = client

			self.send(client, "Welcome to Internet Tic-Tac-Toe!")
			self.prompt(client)

			print(f"Connection from {address}")

		except OSError as exc:
			print(f"Accept error: {exc}")

	def read_client(self, sock):
		#Read incoming data from a client socket.
		#Buffer the data until a complete line is received.
		#Handle CRLF and CR line endings used by Telnet clients.
		client = self.clients.get(sock)

		if client is None:
			return

		try:
			data = sock.recv(4096)

			if not data:
				self.disconnect(client)
				return

			client.input.extend(data)
			client.input = client.input.replace(b"\r\n", b"\n")
			client.input = client.input.replace(b"\r", b"\n")

			while b"\n" in client.input:
				raw, _, remaining = client.input.partition(b"\n")
				client.input = bytearray(remaining)

				self.process_line(client, raw)

				if sock not in self.clients:
					return

			if len(client.input) > 8192:
				self.send(client, "Error: input line too long.")
				client.input.clear()

		except (ConnectionError, OSError):
			self.disconnect(client)

	def write_client(self, sock):
		#Send data to a client. Remove successfully transmitted sats from the output buffer.
		client = self.clients.get(sock)

		if client is None or not client.output:
			return

		try:
			sent = sock.send(client.output)
			del client.output[:sent]

		except (ConnectionError, OSError):
			self.disconnect(client)

	def start(self):
		"""
		Create the listening socket.
		Allow the server to reuse its port after restarting.
		Bind the server to the specified host and port.
		Begin listening for incoming client connection.
		Use non-blocking sockets so one client cannot stall the server.
		"""
		self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		self.listener.bind((self.host, self.port))
		self.listener.listen()
		self.listener.setblocking(False)

		print(f"Listening on {self.host}:{self.port}")

		try:
			"""
			Wait for sockets to be readable, writeable. Report exceptional conditions
			Disconnect clients whose sockets report errors.
			Process new connections and incoming client messages.
			Send messages to clients when their sockets are ready to accept
			outgoing messages.
			"""
			while self.running:
				readers = [self.listener, *self.clients.keys()]
				writers = [sock for sock, client in self.clients.items() if client.output]

				try:
					readable, writable, exceptional = select.select(
						readers, writers, readers, 1.0
					)
				except OSError as exc:
					print(f"select error: {exc}")
					continue

				for sock in exceptional:
					client = self.clients.get(sock)
					if client:
						self.disconnect(client)

				for sock in readable:
					if sock is self.listener:
						self.accept_connection()
					else:
						self.read_client(sock)

				for sock in writable:
					self.write_client(sock)

		#Let the server shut down with ctrl + c
		except KeyboardInterrupt:
			print("\nShutting down...")

		#Disconnect all remaining clients and release their resources when the server shuts down.
		finally: 
			for client in list(self.clients.values()):
				self.disconnect(client)

			if self.listener:
				self.listener.close()

			self.accounts.close()


def main():
	#Configure the command line arguments for starting the server.
	parser = argparse.ArgumentParser(description="Internet Tic-Tac-Toe server")

	#The network interface, the TCP port, and the account database configuration.
	parser.add_argument("--host", default="0.0.0.0")
	parser.add_argument("--port", type=int, default=55551)
	parser.add_argument("--database", default="accounts.db")

	args = parser.parse_args()

	#Make sure the TCP port is within a valid range.
	if not 1 <= args.port <= 65535:
		parser.error("port must be between 1 and 65535")

	#Create the server using the supplied configuration
	server = TicTacToeServer(args.host, args.port, args.database)

	#Start accepting and processing clients.
	#If an OSError occurs, report the error and stop the program.
	try:
		server.start()
	except OSError as exc:
		print(f"Could not start server: {exc}", file=sys.stderr)
		sys.exit(1)


if __name__ == "__main__":
	main()
