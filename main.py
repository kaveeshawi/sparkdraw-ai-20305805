import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from routes import feedback, sentiment, health_score, upsell, estimator, brief, digest, invoice_reminder

app = FastAPI(title="Sparkdraw AI Microservice", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"success": False, "message": str(exc)},
    )


@app.get("/health")
def health_check():
    return {
        "success": True,
        "service": "sparkdraw-ai",
        "version": "1.0",
        "provider": os.getenv("AI_PROVIDER", "openai"),
    }


@app.get("/")
def root():
    return {"success": True, "service": "sparkdraw-ai", "status": "running"}


app.include_router(feedback.router,     prefix="/analyze-feedback", tags=["NLP"])
app.include_router(sentiment.router,    prefix="/sentiment",        tags=["Sentiment"])
app.include_router(health_score.router, prefix="/health-score",     tags=["Health"])
app.include_router(upsell.router,       prefix="/upsell",           tags=["Upsell"])
app.include_router(estimator.router,    prefix="/estimate-hours",   tags=["Estimator"])
app.include_router(brief.router,        prefix="/brief-generator",  tags=["Brief"])
app.include_router(digest.router,       prefix="/digest",           tags=["Digest"])
app.include_router(invoice_reminder.router, prefix="/invoice-reminder", tags=["InvoiceReminder"])
