class AgentPipeline:
    def __init__(self, router):
        self.router = router

    def run(self, model_name: str, prompt: str):
        adapter = self.router.route(model_name)
        response = adapter.generate(prompt)
        return response
