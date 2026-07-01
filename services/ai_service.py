import os
import json
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

# All OpenAI calls are centralised here — never call OpenAI directly from routes.
class AIService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    async def _chat(self, system: str, user: str) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": user},
            ],
        )
        return json.loads(response.choices[0].message.content)

    async def analyze_feedback(self, feedback_text: str, project_type: str | None) -> dict:
        system = "You are a senior technical project manager at a digital agency."
        user = (
            f"A client has submitted the following feedback for a {project_type or 'general'} project:\n"
            f"'{feedback_text}'\n\n"
            "Convert this into structured developer tasks. Respond ONLY in valid JSON with no extra text:\n"
            '{"title": string, "category": string (ui|backend|content|design|bug), '
            '"priority": string (low|medium|high), "subtasks": [string] (max 4), '
            '"assigned_role": string (developer|designer|both), "estimated_hours": integer}'
        )
        return await self._chat(system, user)

    async def analyze_sentiment(self, message_text: str) -> dict:
        system = (
            "Analyse client message sentiment. "
            "Return JSON: {score: float between -1 and 1, label: 'positive'|'neutral'|'negative'}"
        )
        return await self._chat(system, message_text)

    async def estimate_hours(self, task_title: str, task_description: str, project_type: str) -> dict:
        system = "You are a senior project manager at a digital agency."
        user = (
            f"Estimate hours for this task:\n"
            f"Task: {task_title}\n"
            f"Description: {task_description or 'N/A'}\n"
            f"Project type: {project_type}\n\n"
            "Return ONLY valid JSON: "
            "{ 'hours': integer (1-40), 'reasoning': string (one sentence) }"
        )
        return await self._chat(system, user)

    async def generate_brief(
        self,
        project_name: str,
        project_type: str,
        budget: float,
        duration_weeks: int,
        service_description: str = "",
    ) -> dict:
        system = "You are a senior digital agency project manager."
        service_context = (
            f"What this service typically involves: {service_description}\n"
            if service_description else ""
        )
        user = (
            f"Create a project brief:\n"
            f"Project: {project_name}\n"
            f"Type: {project_type}\n"
            f"{service_context}"
            f"Budget: ${budget}\n"
            f"Duration: {duration_weeks} weeks\n\n"
            "Use the service description (if given) to predict realistic, service-specific "
            "milestones and tasks — not generic ones.\n"
            "Return ONLY valid JSON:\n"
            "{ 'milestones': [ { 'title': string, 'due_offset_days': integer, 'description': string } ] (4-6 milestones),\n"
            "  'estimated_hours': integer,\n"
            "  'suggested_phases': [string] (3-4 phases),\n"
            "  'risks': [string] (2-3 risks) }"
        )
        return await self._chat(system, user)

    async def generate_digest(self, project_name: str, client_name: str, events_summary: str) -> dict:
        system = "You are a project manager writing a weekly update for a non-technical client."
        user = (
            f"Project: {project_name}\n"
            f"Client: {client_name}\n"
            f"This week's activity summary: {events_summary}\n\n"
            "Write a friendly, professional 3-4 sentence weekly digest. No technical jargon.\n"
            "Focus on progress made, what is coming next, and any items needing client attention.\n"
            "Return ONLY valid JSON: { 'summary': string }"
        )
        return await self._chat(system, user)
