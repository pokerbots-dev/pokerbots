class Bot:
    def act(self, state):
        if "check" in state["legal"]:
            return ("check",)
        return ("fold",)
