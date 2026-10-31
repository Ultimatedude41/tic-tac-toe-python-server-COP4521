class Game:
	def __init__(self, player_x, player_o):
		#Inisialize the players, the board, the turn, and the winner and draw state.
		self.players = {"X": player_x, "O": player_o}
		self.board = [[" " for _ in range(3)] for _ in range(3)]
		self.turn = "X"
		self.winner = None
		self.draw = False

	def render(self):
		#Make the top of the board with the column numbers.
		lines = ["    1   2   3", "  +---+---+---+"]

		#For each row of the board, replace empty cells with blank cells.
		#Add the row letter and its contents to the board.
		#And add the horizontal line between the rows.
		for r, row in enumerate(self.board):
			cells = [cell if cell != " " else " " for cell in row]
			lines.append(f"{'ABC'[r]} | " + " | ".join(cells) + " |")
			lines.append("  +---+---+---+")
		#The board is returned as a string.
		return "\n".join(lines)

	def move(self, username, coordinate):
		#If the game is finished, stop players from making moves.
		if self.winner or self.draw:
			return False, "This game has already finished."

		#Check to see who's turn it is.
		if self.players[self.turn].casefold() != username.casefold():
			return False, "It is not your turn."

		#Error check to see if the format is correct.
		coordinate = coordinate.upper()
		if (len(coordinate) != 2 or coordinate[0] not in "ABC" or coordinate[1] not in "123"):
			return False, "Invalid move. Use A1 through C3."

		#Convert the row letter and column number into the board index.
		r = ord(coordinate[0]) - ord("A")
		c = int(coordinate[1]) - 1

		#Check to see if the coordinate has been chosen.
		if self.board[r][c] != " ":
			return False, "That square is already occupied."

		#Get the player's mark and place it.
		mark = self.turn
		self.board[r][c] = mark

		#See if the player has won, if it's a draw, or if the game is ongoing.
		if self._has_won(mark):
			self.winner = username
		elif all(cell != " " for row in self.board for cell in row):
			self.draw = True
		else:
			self.turn = "O" if self.turn == "X" else "X"

		#If True is returned, alert the player that the move was accepted.
		return True, "Move accepted."

	def _has_won(self, mark):
		#Check to see if the player has won by checking the rows, then the columns,
		#and lastly the diagonals.
		lines = list(self.board)
		lines += [[self.board[r][c] for r in range(3) for c in range(3)]]
		lines += [[self.board[i][i] for i in range(3)], [self.board[i][2 - i] for i in range(3)],]
		return any(all(cell == mark for cell in line) for line in lines)

	def is_finished(self):
		#Return True if someone has won or if it's a draw.
		return self.winner is not None or self.draw

	def player_mark(self, username):
		#Go through both players and their assignmed marks.
		for mark, player in self.players.items():
			if player.casefold() == username.casefold():
				return mark
		return None

