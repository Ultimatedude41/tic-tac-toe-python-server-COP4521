
class Game:
	def __init__(self, player_x, player_o):
		# player_x and player_o are usernames.
		self.players = {"X": player_x, "O": player_o}
		self.board = [[" " for _ in range(3)] for _ in range(3)]
		self.turn = "X"
		self.winner = None
		self.draw = False

	def render(self):
		lines = ["    1   2   3", "  +---+---+---+"]
		for r, row in enumerate(self.board):
			cells = [cell if cell != " " else " " for cell in row]
			lines.append(
			f"{'ABC'[r]} | "
			+ " | ".join(cells)
			+ " |"
			)
			lines.append("  +---+---+---+")
		return "\n".join(lines)

	def move(self, username, coordinate):
		if self.winner or self.draw:
			return False, "This game has already finished."

		if self.players[self.turn].casefold() != username.casefold():
			return False, "It is not your turn."

		coordinate = coordinate.upper()
		if (
			len(coordinate) != 2
			or coordinate[0] not in "ABC"
			or coordinate[1] not in "123"
		):
			return False, "Invalid move. Use A1 through C3."

		r = ord(coordinate[0]) - ord("A")
		c = int(coordinate[1]) - 1

		if self.board[r][c] != " ":
			return False, "That square is already occupied."

		mark = self.turn
		self.board[r][c] = mark

		if self._has_won(mark):
			self.winner = username
		elif all(cell != " " for row in self.board for cell in row):
			self.draw = True
		else:
			self.turn = "O" if self.turn == "X" else "X"

		return True, "Move accepted."

	def _has_won(self, mark):
		lines = list(self.board)
		lines += [
			[self.board[r][c] for r in range(3)
			for c in range(3)]
		]
		lines += [
			[self.board[i][i] for i in range(3)],
			[self.board[i][2 - i] for i in range(3)],
		]
		return any(all(cell == mark for cell in line) for line in lines)

	def is_finished(self):
		return self.winner is not None or self.draw

	def player_mark(self, username):
		for mark, player in self.players.items():
			if player.casefold() == username.casefold():
				return mark
		return None

