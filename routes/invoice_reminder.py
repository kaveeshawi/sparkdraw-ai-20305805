from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from services.ai_service import AIService

router = APIRouter()
ai_service = AIService()


class InvoiceReminderRequest(BaseModel):
    invoice_id: Optional[int] = None
    invoice_number: str
    client_name: str
    project_name: str = "your project"
    agency_name: str = "our team"
    amount: Optional[float] = None
    amount_label: str = "the outstanding balance"
    due_date: Optional[str] = None
    status: str = "sent"
    notes: Optional[str] = None


def _fallback(req: InvoiceReminderRequest) -> dict:
    due_line = (
        f"This invoice was due on {req.due_date} and remains unpaid."
        if req.due_date and req.status == "overdue"
        else (f"Payment is due by {req.due_date}." if req.due_date else "Please arrange payment at your earliest convenience.")
    )
    subject = (
        f"Overdue invoice {req.invoice_number} — friendly reminder"
        if req.status == "overdue"
        else f"Reminder: invoice {req.invoice_number} for {req.project_name}"
    )
    body = (
        f"Hi {req.client_name},\n\n"
        f"I hope you are well. This is a friendly reminder regarding invoice {req.invoice_number} "
        f"({req.amount_label}) for {req.project_name}.\n\n"
        f"{due_line}\n\n"
        "You can pay securely through your client portal, or reply to this message if you have any questions.\n\n"
        f"Thank you,\n{req.agency_name}"
    )
    return {"subject": subject, "body": body, "source": "fallback"}


def _validate(data: dict, req: InvoiceReminderRequest) -> dict:
    if not isinstance(data, dict):
        return _fallback(req)
    subject = data.get("subject")
    body = data.get("body")
    if not isinstance(subject, str) or not subject.strip() or not isinstance(body, str) or not body.strip():
        return _fallback(req)
    return {"subject": subject.strip(), "body": body.strip(), "source": "ai"}


@router.post("")
async def invoice_reminder(req: InvoiceReminderRequest):
    try:
        raw = await ai_service.generate_invoice_reminder(
            invoice_number=req.invoice_number,
            client_name=req.client_name,
            project_name=req.project_name,
            agency_name=req.agency_name,
            amount_label=req.amount_label,
            due_date=req.due_date,
            status=req.status,
            notes=req.notes,
        )
    except Exception:
        return {"success": True, "data": _fallback(req)}

    return {"success": True, "data": _validate(raw, req)}
