import json
import logging
from agent.base import BaseAgent

class Agent(BaseAgent):
    def __init__(self, model_name=None):
        super().__init__(model_name)

    def run(self, user_query: str, tool_definitions: list = None) -> dict:
        """
        Runs the agent to process a user query.

        Args:
            user_query (str): The user's query.
            tool_definitions (list): List of available tool definitions.

        Returns:
            dict: The tool call plan from the LLM.
        """
        prompt = self._construct_prompt(user_query, tool_definitions)
        logging.debug(f"Agent Prompt: {prompt}")
        try:
            # Enforce JSON output for reliability
            config = {"response_mime_type": "application/json"}
            response = self.llm.generate_content(prompt, config=config)
            logging.debug(f"Agent Raw Response: {response.text}")
        except Exception as e:
            logging.error(f"Agent Generation Error: {e}")
            return {"error": str(e)}

        try:
            # With JSON mode, response.text should be valid JSON directly
            plan = json.loads(response.text)
            return plan
        except json.JSONDecodeError:
            # Handle cases where the LLM doesn't return valid JSON
            return {"error": "Invalid JSON response from LLM", "raw_response": response.text}

    def _construct_prompt(self, user_query: str, tool_definitions: list = None) -> str:
        """
        Constructs the prompt for the LLM.

        Args:
            user_query (str): The user's query.
            tool_definitions (list): List of tool definitions.

        Returns:
            str: The prompt for the LLM.
        """
        tool_description = json.dumps(tool_definitions, indent=2) if tool_definitions else "No tools available."

        prompt = f"""
        You are an AI agent that helps users analyze their stock portfolio.
        Based on the user's query, choose the best tool to use and return the tool name and parameters as a JSON object.

        User Query: "{user_query}"

        Available Tools:
        {tool_description}

        Respond with a JSON object in the following format:
        {{
            "tool_name": "<tool_name>",
            "parameters": {{
                "<parameter_name>": "<parameter_value>"
            }}
        }}
        """
        return prompt