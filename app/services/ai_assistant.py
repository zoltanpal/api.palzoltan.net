from openai import OpenAI

class OpenAIAssistant:
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key is required to initialize OpenAIAssistant")
        
        self.client = OpenAI(api_key=api_key)
        self.model = "gpt-4.1-mini"

    def send_message(self, prompt: str) -> str:
        response = self.client.responses.create(
            model=self.model,
            input=prompt
        )
        return response.output_text