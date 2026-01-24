class ModelRouter:
    def __init__(self, adapters: dict):
        self.adapters = adapters  # name -> IMCPAdapter

    def route(self, model_name: str):
        return self.adapters[model_name]
