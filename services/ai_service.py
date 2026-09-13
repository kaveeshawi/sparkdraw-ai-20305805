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
        requirements: str = "",
        default_hours: int | None = None,
        default_budget: float | None = None,
        suggested_roles: list | None = None,
        package_name: str = "",
        includes: str = "",
        available_packages: list | None = None,
        lock_custom_package: bool = False,
    ) -> dict:
        system = (
            "You are a senior digital agency project manager. "
            "Return ONLY valid JSON. Never invent client personal data."
        )
        service_context = (
            f"Service category description: {service_description}\n"
            if service_description else ""
        )
        packages = available_packages or []
        catalog_lines = []
        for p in packages:
            if not isinstance(p, dict) or not p.get("name"):
                continue
            catalog_lines.append(
                f"- {p['name']}: hours={p.get('duration_hours')}, price={p.get('price')}, "
                f"roles={', '.join(p.get('suggested_roles') or [])}, "
                f"includes={(p.get('includes') or '')[:280]}"
            )
        catalog_context = ""
        if catalog_lines and not lock_custom_package:
            catalog_context = (
                "Available packages for this service:\n"
                + "\n".join(catalog_lines)
                + "\n"
            )
        package_context = ""
        if package_name:
            package_context += f"Working package name: {package_name}\n"
        if includes:
            package_context += f"Working package includes (user-edited — respect these):\n{includes}\n"
        if lock_custom_package:
            if default_hours is not None:
                package_context += (
                    f"PREVIOUS hours estimate (outdated if scope grew — do NOT reuse blindly): {default_hours}\n"
                )
            if default_budget is not None:
                package_context += (
                    f"PREVIOUS budget estimate (outdated if scope grew — do NOT reuse blindly): {default_budget}\n"
                )
            if suggested_roles:
                package_context += (
                    f"PREVIOUS roles (expand when scope grew): {', '.join(suggested_roles)}\n"
                )
        else:
            if default_hours is not None:
                package_context += f"Package duration hours: {default_hours}\n"
            if default_budget is not None:
                package_context += f"Package price / budget: {default_budget}\n"
            if suggested_roles:
                package_context += f"Package suggested roles: {', '.join(suggested_roles)}\n"
        req_context = f"Client/project requirements:\n{requirements}\n" if requirements else ""

        if lock_custom_package:
            strategy = (
                "LOCKED CUSTOM PACKAGE MODE (mandatory):\n"
                "- Do NOT switch to any catalog package (Starter/Pro/Enterprise/etc).\n"
                "- Keep package_match='custom'.\n"
                "- Keep or lightly improve the same custom package name.\n"
                "- Keep the user's includes list as the scope source of truth "
                "(you may clarify wording, but keep every feature they listed).\n"
                "- MUST recalculate estimated_hours, estimated_budget, AND suggested_roles "
                "from the FULL current includes list — not from previous estimates.\n"
                "- If larger features were added (mobile app, AI/analytics, integrations, SMS, "
                "admin/roles, payments, multi-platform), INCREASE hours and budget substantially.\n"
                "- Example: a small booking MVP (~40h / low budget) becomes much larger when "
                "mobile + AI dashboard + integrations are added (often 120–250+ hours).\n"
                "- Expand suggested_roles for larger scope (Designer, Developer, QA, etc.) — "
                "do not keep only Project Manager + Team Member when the scope is large.\n"
                "- Put recalculated hours/price/roles in BOTH top-level fields AND custom_package.\n"
                "- MUST rebuild the full project plan from the updated includes: new milestones, "
                "tasks, brief_summary, suggested_phases, risks, and suggested_duration_weeks.\n"
                "- Do NOT reuse a previous small plan. Every major include (mobile, AI, integrations, "
                "SMS, admin/roles, etc.) should appear in at least one milestone or task.\n"
                "- Generate milestones/tasks whose hours SUM near estimated_hours "
                "(more milestones/tasks when scope is larger).\n"
            )
        else:
            strategy = (
                "Decide package strategy:\n"
                "1) If the user already provided/edited a package name + includes, treat those as the source of truth "
                "and refine the plan around them (prefer package_match='custom' unless they exactly match a catalog package).\n"
                "2) Else if requirements fit an available package well → package_match='existing' and suggested_package=exact catalog name.\n"
                "3) Else → package_match='custom' and invent a tailored custom_package "
                "(name, includes, duration_hours, price, suggested_roles) for THIS project only.\n"
                "Do NOT force a poor catalog fit. Prefer custom when scope is between tiers or clearly different.\n"
            )

        user = (
            f"Create a project setup plan:\n"
            f"Project: {project_name}\n"
            f"Service type: {project_type}\n"
            f"{service_context}"
            f"{catalog_context}"
            f"{package_context}"
            f"{req_context}"
            f"Hint budget (may be 0): {budget}\n"
            f"Hint duration weeks: {duration_weeks}\n\n"
            f"{strategy}"
            "Then plan milestones/tasks from the chosen package priors + requirements.\n"
            "Flag vague requirements that risk scope creep.\n"
            "Return ONLY valid JSON with this shape:\n"
            "{\n"
            "  'package_match': 'existing'|'custom',\n"
            "  'suggested_package': string,\n"
            "  'package_match_reason': string,\n"
            "  'custom_package': null | {\n"
            "      'name': string,\n"
            "      'includes': string (newline bullet list),\n"
            "      'duration_hours': integer,\n"
            "      'price': number,\n"
            "      'suggested_roles': [string]\n"
            "  },\n"
            "  'milestones': [ {\n"
            "      'title': string,\n"
            "      'due_offset_days': integer,\n"
            "      'description': string,\n"
            "      'tasks': [ { 'title': string, 'priority': 'low'|'medium'|'high', 'estimated_hours': integer } ] (2-6 tasks)\n"
            "  } ] (3-6 milestones),\n"
            "  'estimated_hours': integer,\n"
            "  'estimated_budget': number,\n"
            "  'suggested_duration_weeks': integer,\n"
            "  'suggested_roles': [string] (use the agency's role names when provided),\n"
            "  'suggested_phases': [string] (3-4),\n"
            "  'risks': [string] (2-3),\n"
            "  'brief_summary': string (2-4 sentences),\n"
            "  'confidence': 'high'|'medium'|'low',\n"
            "  'confidence_reason': string,\n"
            "  'scope_creep_risk': boolean,\n"
            "  'scope_creep_notes': [string]\n"
            "}"
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

    async def generate_invoice_reminder(
        self,
        invoice_number: str,
        client_name: str,
        project_name: str,
        agency_name: str,
        amount_label: str,
        due_date: str | None,
        status: str,
        notes: str | None = None,
    ) -> dict:
        system = (
            "You draft polite payment reminder emails for a creative digital agency. "
            "Never invent payment links. Keep tone professional and friendly. "
            "Do not claim the email was already sent."
        )
        user = (
            f"Invoice: {invoice_number}\n"
            f"Client: {client_name}\n"
            f"Project: {project_name}\n"
            f"Agency: {agency_name}\n"
            f"Amount: {amount_label}\n"
            f"Due date: {due_date or 'not set'}\n"
            f"Status: {status}\n"
            f"Notes: {notes or 'none'}\n\n"
            "Write a short payment reminder the agency can copy into email.\n"
            "Return ONLY valid JSON: { 'subject': string, 'body': string }"
        )
        return await self._chat(system, user)
