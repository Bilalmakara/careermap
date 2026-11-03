import osmium

class TestHandler(osmium.SimpleHandler):
    def __init__(self):
        super().__init__()
        self.count = 0

    def node(self, n):
        self.count += 1

print("PyOsmium test handler compiled successfully.")

