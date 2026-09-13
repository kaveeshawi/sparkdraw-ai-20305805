from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import List, Optional

from services.ai_service import AIService

router = APIRouter()
ai_service = AIService()

HEAVY_SCOPE_KEYWORDS = (
    "mobile",
    "ios",
    "android",
    "app store",
    "ai analytics",
    "analytics",
    "dashboard",
    "integration",
    "sms",
    " api",
    "payment",
    "realtime",
    "real-time",
    "machine learning",
    "admin",
    "role management",
    "notification",
)


def _feature_count(includes: str) -> int:
    text = (includes or "").strip()
    if not text:
        return 0
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    bullets = [
        ln for ln in lines
        if ln.startswith(("-", "•", "*")) or ln[:2] in ("- ", "• ", "* ")
    ]
    if bullets:
        return len(bullets)
    parts = [p.strip() for p in text.replace(";", ",").split(",") if p.strip()]
    return max(1, len(parts)) if parts else 1


def _heavy_feature_hits(includes: str) -> int:
    text = f" {(includes or '').lower()} "
    hits = 0
    # Prefer specific AI phrasing once
    if "ai " in text or " a.i" in text or "artificial intelligence" in text:
        hits += 1
    for kw in HEAVY_SCOPE_KEYWORDS:
        if kw in ("ai analytics",):
            continue
        if kw in text:
            hits += 1
    return hits


def _scope_floor_hours(includes: str) -> int:
    features = _feature_count(includes)
    heavy = min(_heavy_feature_hits(includes), 5)
    # ~12h per feature + capped bump for heavy items (mobile/AI/etc.)
    return max(24, features * 12 + heavy * 18)


def _milestone_hours_total(milestones: list) -> int:
    total = 0
    for m in milestones or []:
        if not isinstance(m, dict):
            continue
        for t in m.get("tasks") or []:
            if isinstance(t, dict):
                h = t.get("estimated_hours")
                if isinstance(h, (int, float)) and not isinstance(h, bool):
                    total += int(h)
    return total


def _scale_milestones_to_hours(milestones: list, target_hours: int) -> list:
    """Proportionally scale task hours so the plan matches the package estimate."""
    if not milestones or target_hours <= 0:
        return milestones
    current = _milestone_hours_total(milestones)
    if current <= 0:
        return milestones
    # Only scale when plan is clearly undersized vs package hours
    if current >= target_hours * 0.75:
        return milestones
    ratio = target_hours / float(current)
    scaled = []
    for m in milestones:
        if not isinstance(m, dict):
            continue
        tasks = []
        for t in m.get("tasks") or []:
            if not isinstance(t, dict):
                continue
            h = t.get("estimated_hours")
            if isinstance(h, (int, float)) and not isinstance(h, bool):
                h = max(1, int(round(h * ratio)))
            tasks.append({**t, "estimated_hours": h})
        scaled.append({**m, "tasks": tasks})
    return scaled


def _feature_milestones(includes: str, target_hours: int) -> list:
    """Build a scope-aware plan skeleton when includes grew a lot."""
    text = f" {(includes or '').lower()} "
    phases = [
        ("Discovery & scope lock", "Confirm requirements and acceptance criteria", 0.10, 7),
        ("UX / design", "Flows, wireframes, and UI for the custom scope", 0.18, 21),
        ("Core build", "Primary product features from the package includes", 0.28, 42),
    ]
    if any(k in text for k in ("integration", "sms", "api", "calendar", "webhook", "notification")):
        phases.append(("Integrations", "Third-party connections, SMS, and notifications", 0.14, 56))
    if any(k in text for k in ("ai ", "analytics", "dashboard", "machine learning")):
        phases.append(("AI & analytics", "Analytics dashboard and intelligent features", 0.14, 70))
    if any(k in text for k in ("mobile", "ios", "android", "app store")):
        phases.append(("Mobile delivery", "Mobile app experience and release prep", 0.14, 84))
    if any(k in text for k in ("admin", "role", "permission", "auth")):
        phases.append(("Admin & roles", "Admin tooling and role-based access", 0.10, 90))
    phases.append(("QA & launch", "Testing, fixes, and go-live", 0.12, 104))

    # Normalize weights
    weight_sum = sum(p[2] for p in phases) or 1.0
    milestones = []
    for title, desc, weight, offset in phases:
        bucket = max(8, int(round(target_hours * (weight / weight_sum))))
        # Split into 2–3 tasks
        t1 = max(2, int(bucket * 0.45))
        t2 = max(2, int(bucket * 0.35))
        t3 = max(1, bucket - t1 - t2)
        tasks = [
            {"title": f"{title}: setup", "priority": "high", "estimated_hours": t1},
            {"title": f"{title}: build", "priority": "medium", "estimated_hours": t2},
        ]
        if t3 >= 2:
            tasks.append({"title": f"{title}: polish / review", "priority": "medium", "estimated_hours": t3})
        milestones.append({
            "title": title,
            "due_offset_days": offset,
            "description": desc,
            "tasks": tasks,
        })
    return milestones[:6]


def _plan_covers_includes(milestones: list, includes: str) -> bool:
    blob = " ".join(
        f"{m.get('title', '')} {m.get('description', '')} "
        + " ".join(t.get("title", "") for t in (m.get("tasks") or []) if isinstance(t, dict))
        for m in (milestones or []) if isinstance(m, dict)
    ).lower()
    text = f" {(includes or '').lower()} "
    checks = []
    if any(k in text for k in ("mobile", "ios", "android")):
        checks.append(any(k in blob for k in ("mobile", "ios", "android", "app")))
    if any(k in text for k in ("ai ", "analytics", "dashboard")):
        checks.append(any(k in blob for k in ("ai", "analytics", "dashboard")))
    if any(k in text for k in ("integration", "sms", "api", "calendar")):
        checks.append(any(k in blob for k in ("integration", "sms", "api", "calendar", "notification")))
    if not checks:
        return True
    return all(checks)


def _adjust_locked_estimates(
    hours: int,
    budget: float,
    includes: str,
    previous_hours: Optional[int],
    previous_budget: Optional[float],
) -> tuple[int, float]:
    """When user expands custom package includes, don't let estimates stay stuck."""
    floor_hours = _scope_floor_hours(includes)
    adj_hours = max(int(hours or 0), floor_hours)

    prev_h = int(previous_hours) if previous_hours else None
    prev_b = float(previous_budget) if previous_budget is not None else None

    # AI often reuses previous numbers — force bump when scope clearly outgrew them
    if prev_h and adj_hours <= int(prev_h * 1.15) and floor_hours > int(prev_h * 1.2):
        adj_hours = floor_hours

    rate = 50.0
    if prev_h and prev_b and prev_h > 0:
        rate = max(35.0, float(prev_b) / float(prev_h))

    adj_budget = max(float(budget or 0), adj_hours * rate)
    if prev_b is not None and adj_budget <= prev_b * 1.15 and adj_hours > (prev_h or 0) * 1.2:
        adj_budget = round(adj_hours * rate, 2)

    return adj_hours, float(adj_budget)


FALLBACK_BRIEF = {
    "milestones": [
        {
            "title": "Discovery & Kickoff",
            "due_offset_days": 7,
            "description": "Align on goals and scope",
            "tasks": [
                {"title": "Kickoff meeting", "priority": "high", "estimated_hours": 2},
                {"title": "Requirements workshop", "priority": "high", "estimated_hours": 4},
            ],
        },
        {
            "title": "Design Phase",
            "due_offset_days": 21,
            "description": "Wireframes and visual design",
            "tasks": [
                {"title": "Wireframes", "priority": "medium", "estimated_hours": 8},
                {"title": "UI design", "priority": "medium", "estimated_hours": 12},
            ],
        },
        {
            "title": "Development",
            "due_offset_days": 42,
            "description": "Build and integrate features",
            "tasks": [
                {"title": "Core build", "priority": "high", "estimated_hours": 24},
                {"title": "Integrations", "priority": "medium", "estimated_hours": 8},
            ],
        },
        {
            "title": "QA & Launch",
            "due_offset_days": 56,
            "description": "Testing and go-live",
            "tasks": [
                {"title": "QA pass", "priority": "high", "estimated_hours": 6},
                {"title": "Launch checklist", "priority": "high", "estimated_hours": 4},
            ],
        },
    ],
    "estimated_hours": 80,
    "estimated_budget": 3500,
    "suggested_duration_weeks": 8,
    "suggested_roles": ["Project Manager", "Team Member"],
    "suggested_phases": ["Discovery", "Design", "Development", "Launch"],
    "risks": ["Scope creep from unclear requirements", "Client approval delays"],
    "brief_summary": "A structured delivery plan covering discovery, design, build, and launch.",
    "confidence": "medium",
    "confidence_reason": "Based on typical agency package defaults.",
    "scope_creep_risk": False,
    "scope_creep_notes": [],
}


class PackageOption(BaseModel):
    name: str
    includes: str = ""
    duration_hours: Optional[int] = None
    price: Optional[float] = None
    suggested_roles: List[str] = Field(default_factory=list)


class BriefRequest(BaseModel):
    project_name: str
    project_type: str
    service_description: str = ""
    package_name: str = ""
    includes: str = ""
    requirements: str = ""
    budget: float = 0
    duration_weeks: int = 4
    default_hours: Optional[int] = None
    default_budget: Optional[float] = None
    suggested_roles: List[str] = Field(default_factory=list)
    available_packages: List[PackageOption] = Field(default_factory=list)
    lock_custom_package: bool = False


def _clean_tasks(raw) -> list:
    if not isinstance(raw, list):
        return []
    out = []
    for t in raw[:8]:
        if not isinstance(t, dict) or not isinstance(t.get("title"), str):
            continue
        title = t["title"].strip()
        if not title:
            continue
        priority = t.get("priority", "medium")
        if priority not in ("low", "medium", "high"):
            priority = "medium"
        hours = t.get("estimated_hours")
        if isinstance(hours, (int, float)) and not isinstance(hours, bool):
            hours = max(1, int(hours))
        else:
            hours = None
        out.append({"title": title, "priority": priority, "estimated_hours": hours})
    return out


def _validate_brief(data: dict, req: BriefRequest) -> dict:
    if not isinstance(data, dict):
        base = dict(FALLBACK_BRIEF)
    else:
        base = data

    milestones = base.get("milestones")
    if not isinstance(milestones, list) or len(milestones) < 3:
        result = dict(FALLBACK_BRIEF)
    else:
        clean_milestones = []
        for m in milestones[:6]:
            if not isinstance(m, dict) or not isinstance(m.get("title"), str):
                continue
            clean_milestones.append({
                "title": m["title"].strip(),
                "due_offset_days": int(m.get("due_offset_days", 7)) if isinstance(m.get("due_offset_days"), (int, float)) else 7,
                "description": str(m.get("description", "")).strip(),
                "tasks": _clean_tasks(m.get("tasks")),
            })
        if len(clean_milestones) < 3:
            result = dict(FALLBACK_BRIEF)
        else:
            result = {"milestones": clean_milestones}

    hours = base.get("estimated_hours")
    if not isinstance(hours, (int, float)) or isinstance(hours, bool):
        hours = req.default_hours or FALLBACK_BRIEF["estimated_hours"]
    result["estimated_hours"] = max(1, int(hours))

    budget = base.get("estimated_budget")
    if not isinstance(budget, (int, float)) or isinstance(budget, bool):
        budget = req.default_budget if req.default_budget is not None else (
            req.budget if req.budget else FALLBACK_BRIEF["estimated_budget"]
        )
    result["estimated_budget"] = max(0, float(budget))

    weeks = base.get("suggested_duration_weeks")
    if not isinstance(weeks, (int, float)) or isinstance(weeks, bool):
        weeks = req.duration_weeks or FALLBACK_BRIEF["suggested_duration_weeks"]
    result["suggested_duration_weeks"] = max(1, int(weeks))

    roles = base.get("suggested_roles")
    if not isinstance(roles, list) or not all(isinstance(r, str) for r in roles):
        roles = req.suggested_roles or FALLBACK_BRIEF["suggested_roles"]
    result["suggested_roles"] = [r.strip() for r in roles[:6] if isinstance(r, str) and r.strip()]

    phases = base.get("suggested_phases")
    if not isinstance(phases, list) or not all(isinstance(p, str) for p in phases):
        phases = FALLBACK_BRIEF["suggested_phases"]
    result["suggested_phases"] = phases[:4]

    risks = base.get("risks")
    if not isinstance(risks, list) or not all(isinstance(r, str) for r in risks):
        risks = FALLBACK_BRIEF["risks"]
    result["risks"] = risks[:3]

    summary = base.get("brief_summary")
    result["brief_summary"] = summary.strip() if isinstance(summary, str) and summary.strip() else FALLBACK_BRIEF["brief_summary"]

    conf = base.get("confidence")
    if conf not in ("high", "medium", "low"):
        conf = "medium"
    result["confidence"] = conf

    reason = base.get("confidence_reason")
    result["confidence_reason"] = reason.strip() if isinstance(reason, str) and reason.strip() else FALLBACK_BRIEF["confidence_reason"]

    # Heuristic scope-creep flag from vague requirements
    vague = ("etc", "make it pop", "as needed", "tbd", "nice to have", "whatever", "something like")
    req_text = (req.requirements or "").lower()
    notes = []
    if req_text:
        for v in vague:
            if v in req_text:
                notes.append(f'Vague phrasing detected: "{v}"')
        if len(req_text.split()) < 12:
            notes.append("Requirements are very short — scope may expand later.")
    ai_flag = bool(base.get("scope_creep_risk")) if isinstance(base.get("scope_creep_risk"), bool) else False
    ai_notes = base.get("scope_creep_notes")
    if isinstance(ai_notes, list):
        notes.extend([str(n) for n in ai_notes if isinstance(n, str)][:3])
    result["scope_creep_risk"] = ai_flag or len(notes) > 0
    result["scope_creep_notes"] = notes[:4]

    # Ensure milestones always present
    if "milestones" not in result:
        result["milestones"] = FALLBACK_BRIEF["milestones"]

    available_names = [p.name for p in req.available_packages if getattr(p, "name", None)]
    lower_map = {n.lower(): n for n in available_names}

    # User edited / locked a custom package — never switch to catalog
    if req.lock_custom_package:
        custom_raw = base.get("custom_package") if isinstance(base.get("custom_package"), dict) else {}
        name = custom_raw.get("name") if isinstance(custom_raw.get("name"), str) else None
        name = (name or req.package_name or base.get("suggested_package") or "Custom package")
        if not isinstance(name, str):
            name = "Custom package"
        name = name.strip()[:100]

        includes = custom_raw.get("includes") if isinstance(custom_raw.get("includes"), str) else ""
        includes = includes.strip()[:4000] or (req.includes or "").strip()[:4000] or (req.requirements or "").strip()[:800]

        # Prefer AI top-level estimates, then custom_package, then previous defaults
        hours = base.get("estimated_hours")
        if not isinstance(hours, (int, float)) or isinstance(hours, bool):
            hours = custom_raw.get("duration_hours")
        if not isinstance(hours, (int, float)) or isinstance(hours, bool):
            hours = req.default_hours or FALLBACK_BRIEF["estimated_hours"]

        price = base.get("estimated_budget")
        if not isinstance(price, (int, float)) or isinstance(price, bool):
            price = custom_raw.get("price")
        if not isinstance(price, (int, float)) or isinstance(price, bool):
            price = req.default_budget if req.default_budget is not None else FALLBACK_BRIEF["estimated_budget"]

        adj_hours, adj_budget = _adjust_locked_estimates(
            max(1, int(hours)),
            max(0.0, float(price)),
            includes,
            req.default_hours,
            req.default_budget,
        )
        result["estimated_hours"] = adj_hours
        result["estimated_budget"] = adj_budget

        roles_raw = base.get("suggested_roles") if isinstance(base.get("suggested_roles"), list) else []
        if not roles_raw:
            roles_raw = custom_raw.get("suggested_roles") if isinstance(custom_raw.get("suggested_roles"), list) else []
        roles = [str(r).strip() for r in roles_raw if isinstance(r, str) and r.strip()][:6]
        if not roles and req.suggested_roles:
            roles = list(req.suggested_roles)[:6]
        if not roles:
            roles = list(FALLBACK_BRIEF["suggested_roles"])

        # Larger scope → ensure enough role coverage for staffing
        if adj_hours >= 100:
            for extra in ("Designer", "Developer", "QA"):
                if len(roles) >= 5:
                    break
                if not any(extra.lower() in r.lower() for r in roles):
                    roles.append(extra)
        result["suggested_roles"] = roles[:6]

        # Rebuild / scale the project plan so it matches the expanded package
        milestones = result.get("milestones") if isinstance(result.get("milestones"), list) else []
        plan_hours = _milestone_hours_total(milestones)
        needs_rebuild = (
            not milestones
            or plan_hours < adj_hours * 0.55
            or not _plan_covers_includes(milestones, includes)
        )
        if needs_rebuild:
            milestones = _feature_milestones(includes, adj_hours)
        else:
            milestones = _scale_milestones_to_hours(milestones, adj_hours)
        result["milestones"] = milestones

        weeks = max(4, int(round(adj_hours / 20)))
        result["suggested_duration_weeks"] = max(
            int(result.get("suggested_duration_weeks") or 0),
            weeks,
            int(req.duration_weeks or 0) or 0,
        ) or weeks

        phases = []
        for m in milestones:
            title = m.get("title") if isinstance(m, dict) else None
            if isinstance(title, str) and title.strip():
                phases.append(title.strip().split(":")[0].strip())
        if phases:
            result["suggested_phases"] = phases[:4]

        feature_n = _feature_count(includes)
        result["brief_summary"] = (
            f"Custom delivery plan for “{name}” covering {feature_n} scoped features "
            f"(~{adj_hours} hours). Milestones follow the updated package includes — "
            f"including any added integrations, mobile, analytics/AI, and admin work."
        )
        result["confidence_reason"] = (
            "Plan regenerated from the locked custom package includes with recalculated effort."
        )

        reason = base.get("package_match_reason")
        reason = reason.strip() if isinstance(reason, str) and reason.strip() else (
            "Kept your custom package and rebuilt hours, budget, roles, and the project plan from the updated includes."
        )

        result["package_match"] = "custom"
        result["suggested_package"] = name
        result["custom_package"] = {
            "name": name,
            "includes": includes,
            "duration_hours": result.get("estimated_hours"),
            "price": result.get("estimated_budget"),
            "suggested_roles": result.get("suggested_roles") or [],
        }
        result["package_match_reason"] = reason
        return result

    suggested_pkg = base.get("suggested_package")
    if not isinstance(suggested_pkg, str):
        suggested_pkg = ""
    suggested_pkg = suggested_pkg.strip() or (req.package_name or "").strip()

    match_type = base.get("package_match")
    if match_type not in ("existing", "custom"):
        match_type = "existing" if (suggested_pkg and suggested_pkg.lower() in lower_map) else (
            "custom" if suggested_pkg or base.get("custom_package") else ("existing" if available_names else "custom")
        )

    # If AI said existing but name isn't in catalog → treat as custom (don't force a wrong tier)
    if match_type == "existing" and suggested_pkg and suggested_pkg.lower() not in lower_map:
        fuzzy = next(
            (n for n in available_names if suggested_pkg.lower() in n.lower() or n.lower() in suggested_pkg.lower()),
            None,
        )
        if fuzzy:
            suggested_pkg = fuzzy
        else:
            match_type = "custom"

    if match_type == "existing" and not suggested_pkg and available_names:
        suggested_pkg = available_names[0]

    package_reason = base.get("package_match_reason")
    package_reason = package_reason.strip() if isinstance(package_reason, str) and package_reason.strip() else None

    if match_type == "existing" and suggested_pkg and suggested_pkg.lower() in lower_map:
        suggested_pkg = lower_map[suggested_pkg.lower()]
        pkg = next((p for p in req.available_packages if p.name == suggested_pkg), None)
        if pkg:
            if not isinstance(base.get("estimated_hours"), (int, float)) and pkg.duration_hours:
                result["estimated_hours"] = int(pkg.duration_hours)
            if not isinstance(base.get("estimated_budget"), (int, float)) and pkg.price is not None:
                result["estimated_budget"] = float(pkg.price)
            if (not result.get("suggested_roles")) and pkg.suggested_roles:
                result["suggested_roles"] = list(pkg.suggested_roles)[:6]
        result["package_match"] = "existing"
        result["suggested_package"] = suggested_pkg
        result["custom_package"] = None
        result["package_match_reason"] = package_reason or f"Matched catalog package “{suggested_pkg}”."
    else:
        custom_raw = base.get("custom_package") if isinstance(base.get("custom_package"), dict) else {}
        name = custom_raw.get("name") if isinstance(custom_raw.get("name"), str) else suggested_pkg
        name = (name or "Custom package").strip()[:100]
        includes = custom_raw.get("includes") if isinstance(custom_raw.get("includes"), str) else ""
        includes = includes.strip()[:4000] or (req.requirements or "").strip()[:800]
        hours = custom_raw.get("duration_hours")
        price = custom_raw.get("price")
        roles_raw = custom_raw.get("suggested_roles") if isinstance(custom_raw.get("suggested_roles"), list) else []
        roles = [str(r).strip() for r in roles_raw if isinstance(r, str) and r.strip()][:6]
        if isinstance(hours, (int, float)) and not isinstance(hours, bool):
            result["estimated_hours"] = max(1, int(hours))
        if isinstance(price, (int, float)) and not isinstance(price, bool):
            result["estimated_budget"] = max(0, float(price))
        if roles:
            result["suggested_roles"] = roles
        result["package_match"] = "custom"
        result["suggested_package"] = name
        result["custom_package"] = {
            "name": name,
            "includes": includes,
            "duration_hours": result.get("estimated_hours"),
            "price": result.get("estimated_budget"),
            "suggested_roles": result.get("suggested_roles") or [],
        }
        result["package_match_reason"] = package_reason or (
            "Requirements did not fit an existing catalog package closely enough — created a custom package."
        )

    return result


@router.post("")
async def generate_brief(req: BriefRequest):
    try:
        raw = await ai_service.generate_brief(
            project_name=req.project_name,
            project_type=req.project_type,
            budget=req.budget,
            duration_weeks=req.duration_weeks,
            service_description=req.service_description,
            package_name=req.package_name,
            includes=req.includes,
            requirements=req.requirements,
            default_hours=req.default_hours,
            default_budget=req.default_budget,
            suggested_roles=req.suggested_roles,
            available_packages=[p.model_dump() for p in req.available_packages],
            lock_custom_package=req.lock_custom_package,
        )
    except Exception:
        return {"success": True, "data": _validate_brief({}, req)}

    return {"success": True, "data": _validate_brief(raw if isinstance(raw, dict) else {}, req)}
