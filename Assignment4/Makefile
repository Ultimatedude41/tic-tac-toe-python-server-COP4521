PYTHON = python3
PORT = 55555

.PHONY: run check clean

run:
	$(PYTHON) server.py --port $(PORT)

check:
	$(PYTHON) -m py_compile server.py accounts.py games.py

clean:
	rm -rf __pycache__
