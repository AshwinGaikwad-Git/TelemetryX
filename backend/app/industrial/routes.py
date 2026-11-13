import csv
import io
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, File, Header, HTTPException, Query, Request, UploadFile
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.config import get_settings
from app.industrial.auth import Database, Member, audit, current_user, digest, require
from app.industrial.models import (
    Alert,
    AuditEvent,
    IngestionKey,
    Invitation,
    Machine,
    Membership,
    Reading,
    Sensor,
    Site,
    User,
    WorkOrder,
)
from app.industrial.schemas import (
    MachineCreate,
    MachineUpdate,
    MemberCreate,
    RoleUpdate,
    SensorCreate,
    SiteCreate,
    TelemetryBatch,
    TelemetryPoint,
    WorkCreate,
    WorkUpdate,
    utc,
)
from app.industrial.service import ingest, machine_for, machine_snapshot, record, source_checksum

router = APIRouter(prefix="/industrial/companies/{company_id}", tags=["industrial workspaces"])
EDIT = ("admin", "manager", "engineer")


def commit(db: Database) -> None:
    try:
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "A record with this identifier already exists") from error


@router.get("/sites")
def sites(company_id: uuid.UUID, member: Member, db: Database) -> list[dict[str, Any]]:
    return [
        record(site)
        for site in db.scalars(
            select(Site)
            .where(
                Site.company_id == company_id,
            )
            .order_by(Site.name)
        ).all()
    ]


@router.post("/sites", status_code=201)
def add_site(
    company_id: uuid.UUID, req: SiteCreate, member: Member, db: Database
) -> dict[str, Any]:
    require(member, *EDIT)
    site = Site(company_id=company_id, **req.model_dump())
    db.add(site)
    db.flush()
    audit(db, company_id, str(member.user_id), "site.created", site.id)
    commit(db)
    return record(site)


@router.get("/machines")
def machines(
    company_id: uuid.UUID, member: Member, db: Database, site_id: uuid.UUID | None = None
) -> list[dict[str, Any]]:
    query = select(Machine).where(Machine.company_id == company_id)
    if site_id:
        query = query.where(Machine.site_id == site_id)
    return [
        machine_snapshot(db, machine)
        for machine in db.scalars(
            query.order_by(Machine.asset_tag).limit(500),
        ).all()
    ]


@router.post("/machines", status_code=201)
def add_machine(
    company_id: uuid.UUID, req: MachineCreate, member: Member, db: Database
) -> dict[str, Any]:
    require(member, *EDIT)
    site = db.scalars(
        select(Site).where(Site.id == req.site_id, Site.company_id == company_id)
    ).first()
    if not site:
        raise HTTPException(404, "Site not found in this workspace")
    machine = Machine(company_id=company_id, **req.model_dump())
    db.add(machine)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Asset tag already exists in this workspace") from error
    audit(db, company_id, str(member.user_id), "machine.created", machine.id)
    commit(db)
    return machine_snapshot(db, machine)


@router.get("/machines/{machine_id}")
def get_machine(
    company_id: uuid.UUID, machine_id: uuid.UUID, member: Member, db: Database
) -> dict[str, Any]:
    return machine_snapshot(db, machine_for(db, company_id, machine_id))


@router.patch("/machines/{machine_id}")
def update_machine(
    company_id: uuid.UUID, machine_id: uuid.UUID, req: MachineUpdate, member: Member, db: Database
) -> dict[str, Any]:
    require(member, *EDIT)
    machine = machine_for(db, company_id, machine_id)
    machine.operating_state = req.operating_state
    audit(
        db, company_id, str(member.user_id), "machine.state_changed", machine_id, req.model_dump()
    )
    commit(db)
    return machine_snapshot(db, machine)


@router.post("/machines/{machine_id}/sensors", status_code=201)
def add_sensor(
    company_id: uuid.UUID, machine_id: uuid.UUID, req: SensorCreate, member: Member, db: Database
) -> dict[str, Any]:
    require(member, "admin", "engineer")
    machine_for(db, company_id, machine_id)
    count = db.scalar(
        select(func.count()).select_from(Sensor).where(Sensor.machine_id == machine_id)
    )
    if count and count >= 100:
        raise HTTPException(400, "A machine supports at most 100 sensors in this pilot")
    sensor = Sensor(company_id=company_id, machine_id=machine_id, **req.model_dump())
    db.add(sensor)
    try:
        db.flush()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(409, "Sensor key already exists on this machine") from error
    audit(db, company_id, str(member.user_id), "sensor.created", sensor.id, req.model_dump())
    commit(db)
    return record(sensor)


@router.get("/machines/{machine_id}/readings")
def readings(
    company_id: uuid.UUID,
    machine_id: uuid.UUID,
    sensor_key: str,
    member: Member,
    db: Database,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(default=500, ge=1, le=5000),
    before: datetime | None = None,
) -> list[dict[str, Any]]:
    machine_for(db, company_id, machine_id)
    sensor = db.scalars(
        select(Sensor).where(
            Sensor.company_id == company_id,
            Sensor.machine_id == machine_id,
            Sensor.key == sensor_key,
        )
    ).first()
    if not sensor:
        raise HTTPException(404, "Sensor not found")
    if start and end and utc(start) > utc(end):
        raise HTTPException(400, "Start must precede end")
    query = select(Reading).where(Reading.company_id == company_id, Reading.sensor_id == sensor.id)
    if start:
        query = query.where(Reading.timestamp >= utc(start))
    if end:
        query = query.where(Reading.timestamp <= utc(end))
    if before:
        query = query.where(Reading.timestamp < utc(before))
    rows = db.scalars(query.order_by(Reading.timestamp.desc()).limit(limit)).all()
    return [record(row) for row in reversed(rows)]


def ingestion_actor(company_id: uuid.UUID, db: Database, key: str | None) -> str | None:
    if not key:
        return None
    credential = db.scalars(
        select(IngestionKey).where(
            IngestionKey.company_id == company_id,
            IngestionKey.token_hash == digest(key),
            IngestionKey.active.is_(True),
        )
    ).first()
    if not credential:
        raise HTTPException(401, "Ingestion credential is invalid")
    return f"integration:{credential.id}"


@router.post("/telemetry")
def telemetry(
    company_id: uuid.UUID,
    req: TelemetryBatch,
    request: Request,
    db: Database,
    x_ingestion_key: str | None = Header(default=None),
) -> dict[str, Any]:
    actor = ingestion_actor(company_id, db, x_ingestion_key)
    if actor is None:
        user = current_user(request, db)
        member = db.scalars(
            select(Membership).where(
                Membership.company_id == company_id,
                Membership.user_id == user.id,
            )
        ).first()
        if not member:
            raise HTTPException(404, "Workspace not found")
        require(member, *EDIT)
        actor = str(user.id)
    content = json.dumps(req.model_dump(mode="json"), sort_keys=True).encode()
    if len(content) > get_settings().max_upload_size_mb * 1024 * 1024:
        raise HTTPException(413, "Batch exceeds MAX_UPLOAD_SIZE_MB")
    checksum = source_checksum(content)
    directory = get_settings().raw_storage_path / "industrial" / str(company_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{checksum}.json"
    if not path.exists():
        path.write_bytes(content)
    return ingest(db, company_id, actor, req.readings, "api", checksum)


@router.post("/machines/{machine_id}/imports")
async def import_csv(
    company_id: uuid.UUID,
    machine_id: uuid.UUID,
    member: Member,
    db: Database,
    file: UploadFile = File(...),
) -> dict[str, Any]:
    require(member, *EDIT)
    machine_for(db, company_id, machine_id)
    content = await file.read(get_settings().max_upload_size_mb * 1024 * 1024 + 1)
    if len(content) > get_settings().max_upload_size_mb * 1024 * 1024:
        raise HTTPException(413, "Upload exceeds MAX_UPLOAD_SIZE_MB")
    try:
        reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
        if set(reader.fieldnames or []) != {"sensor_key", "timestamp", "value", "unit"}:
            raise HTTPException(400, "CSV headers must be sensor_key,timestamp,value,unit")
        points: list[TelemetryPoint] = []
        for row in reader:
            if len(points) >= 10000:
                raise HTTPException(413, "Import at most 10000 readings per file")
            points.append(TelemetryPoint.model_validate({**row, "machine_id": machine_id}))
        if not points:
            raise HTTPException(400, "CSV contains no readings")
    except (UnicodeDecodeError, csv.Error, ValidationError) as error:
        raise HTTPException(400, f"CSV parsing failed: {error}") from error
    checksum = source_checksum(content)
    directory = get_settings().raw_storage_path / "industrial" / str(company_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{checksum}.csv"
    if not path.exists():
        path.write_bytes(content)
    return ingest(db, company_id, str(member.user_id), points, "csv", checksum)


@router.get("/summary")
def summary(
    company_id: uuid.UUID, member: Member, db: Database, site_id: uuid.UUID | None = None
) -> dict[str, Any]:
    items = machines(company_id, member, db, site_id)
    machine_ids = [item["id"] for item in items]
    alert_count = db.scalar(
        select(func.count())
        .select_from(Alert)
        .where(
            Alert.company_id == company_id,
            Alert.machine_id.in_(machine_ids),
            Alert.status.in_(["open", "acknowledged"]),
        )
    )
    work = db.scalars(
        select(WorkOrder).where(
            WorkOrder.company_id == company_id,
            WorkOrder.machine_id.in_(machine_ids),
        )
    ).all()
    return {
        "machine_count": len(items),
        "online": sum(m["connectivity"] == "online" for m in items),
        "attention": sum(m["health"] == "attention" for m in items),
        "unknown": sum(m["health"] in ("unknown", "insufficient_data") for m in items),
        "active_alerts": alert_count or 0,
        "open_work_orders": sum(w.status not in ("verified", "cancelled") for w in work),
        "recorded_downtime_minutes": sum(
            w.downtime_minutes for w in work if w.status in ("completed", "verified")
        ),
        "scope": "Up to 500 registered machines in the selected workspace/site",
    }


@router.get("/alerts")
def alerts(company_id: uuid.UUID, member: Member, db: Database) -> list[dict[str, Any]]:
    return [
        record(row)
        for row in db.scalars(
            select(Alert)
            .where(
                Alert.company_id == company_id,
            )
            .order_by(Alert.created_at.desc())
            .limit(500)
        ).all()
    ]


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge(
    company_id: uuid.UUID, alert_id: uuid.UUID, member: Member, db: Database
) -> dict[str, Any]:
    require(member, *EDIT, "technician")
    alert = db.scalars(
        select(Alert).where(Alert.company_id == company_id, Alert.id == alert_id)
    ).first()
    if not alert:
        raise HTTPException(404, "Alert not found")
    if alert.status != "open":
        raise HTTPException(409, "Only open alerts can be acknowledged")
    alert.status = "acknowledged"
    alert.acknowledged_by = member.user_id
    audit(db, company_id, str(member.user_id), "alert.acknowledged", alert_id)
    commit(db)
    return record(alert)


@router.get("/work-orders")
def work_orders(company_id: uuid.UUID, member: Member, db: Database) -> list[dict[str, Any]]:
    return [
        record(row)
        for row in db.scalars(
            select(WorkOrder)
            .where(
                WorkOrder.company_id == company_id,
            )
            .order_by(WorkOrder.created_at.desc())
            .limit(500)
        ).all()
    ]


@router.post("/work-orders", status_code=201)
def add_work(
    company_id: uuid.UUID, req: WorkCreate, member: Member, db: Database
) -> dict[str, Any]:
    require(member, *EDIT)
    machine_for(db, company_id, req.machine_id)
    if req.alert_id:
        alert = db.scalars(
            select(Alert).where(
                Alert.id == req.alert_id,
                Alert.company_id == company_id,
                Alert.machine_id == req.machine_id,
            )
        ).first()
        if not alert:
            raise HTTPException(404, "Alert does not belong to this machine")
    check_assignee(db, company_id, req.assigned_to)
    work = WorkOrder(
        company_id=company_id, status="assigned" if req.assigned_to else "open", **req.model_dump()
    )
    db.add(work)
    db.flush()
    audit(db, company_id, str(member.user_id), "work_order.created", work.id)
    commit(db)
    return record(work)


def check_assignee(db: Database, company_id: uuid.UUID, user_id: uuid.UUID | None) -> None:
    if (
        user_id
        and not db.scalars(
            select(Membership).where(
                Membership.company_id == company_id,
                Membership.user_id == user_id,
                Membership.role.in_(["admin", "manager", "engineer", "technician"]),
            )
        ).first()
    ):
        raise HTTPException(400, "Assignee must be a working member of this workspace")


@router.patch("/work-orders/{work_id}")
def update_work(
    company_id: uuid.UUID, work_id: uuid.UUID, req: WorkUpdate, member: Member, db: Database
) -> dict[str, Any]:
    work = db.scalars(
        select(WorkOrder)
        .where(
            WorkOrder.company_id == company_id,
            WorkOrder.id == work_id,
        )
        .with_for_update()
    ).first()
    if not work:
        raise HTTPException(404, "Work order not found")
    require(member, *EDIT, "technician")
    if member.role == "technician" and (
        work.assigned_to != member.user_id
        or req.status not in ("in_progress", "completed")
        or "assigned_to" in req.model_fields_set
    ):
        raise HTTPException(403, "Technicians may progress only their assigned work")
    transitions = {
        "open": {"assigned", "cancelled"},
        "assigned": {"assigned", "in_progress", "cancelled"},
        "in_progress": {"completed", "cancelled"},
        "completed": {"verified", "in_progress"},
        "verified": set(),
        "cancelled": set(),
    }
    if req.status not in transitions[work.status]:
        raise HTTPException(409, f"Cannot move {work.status} to {req.status}")
    if req.status == "verified":
        require(member, *EDIT)
    if "assigned_to" in req.model_fields_set:
        check_assignee(db, company_id, req.assigned_to)
        work.assigned_to = req.assigned_to
    if req.status in ("assigned", "in_progress") and not work.assigned_to:
        raise HTTPException(400, "Assign a team member before starting work")
    if req.status == "completed" and not (req.findings or work.findings).strip():
        raise HTTPException(400, "Record inspection or repair findings before completion")
    for field in ("findings", "component", "downtime_minutes"):
        value = getattr(req, field)
        if value is not None:
            setattr(work, field, value)
    work.status = req.status
    if req.status == "completed":
        work.completed_at = datetime.now(UTC)
    if req.status == "verified":
        work.verified_at = datetime.now(UTC)
    audit(
        db,
        company_id,
        str(member.user_id),
        "work_order.updated",
        work_id,
        req.model_dump(mode="json", exclude_unset=True),
    )
    commit(db)
    return record(work)


@router.get("/members")
def members(company_id: uuid.UUID, member: Member, db: Database) -> list[dict[str, Any]]:
    rows = db.execute(
        select(User, Membership)
        .join(Membership, User.id == Membership.user_id)
        .where(
            Membership.company_id == company_id,
        )
    ).all()
    return [
        {"id": str(user.id), "name": user.name, "email": user.email, "role": entry.role}
        for user, entry in rows
    ]


def member_to_manage(db: Database, company_id: uuid.UUID, user_id: uuid.UUID) -> Membership:
    entries = db.scalars(
        select(Membership)
        .where(
            Membership.company_id == company_id,
        )
        .order_by(Membership.id)
        .with_for_update()
    ).all()
    target = next((entry for entry in entries if entry.user_id == user_id), None)
    if not target:
        raise HTTPException(404, "Member not found")
    if target.role == "admin" and sum(entry.role == "admin" for entry in entries) <= 1:
        raise HTTPException(409, "A workspace must retain at least one administrator")
    return target


def unassign_active_work(db: Database, company_id: uuid.UUID, user_id: uuid.UUID) -> None:
    for work in db.scalars(
        select(WorkOrder).where(
            WorkOrder.company_id == company_id,
            WorkOrder.assigned_to == user_id,
            WorkOrder.status.in_(["assigned", "in_progress"]),
        )
    ).all():
        work.assigned_to = None
        work.status = "open"


@router.patch("/members/{user_id}")
def change_role(
    company_id: uuid.UUID, user_id: uuid.UUID, req: RoleUpdate, member: Member, db: Database
) -> dict[str, str]:
    require(member, "admin")
    target = member_to_manage(db, company_id, user_id)
    target.role = req.role
    if req.role == "viewer":
        unassign_active_work(db, company_id, user_id)
    audit(
        db, company_id, str(member.user_id), "membership.role_changed", user_id, {"role": req.role}
    )
    commit(db)
    return {"role": req.role}


@router.delete("/members/{user_id}", status_code=204)
def remove_member(company_id: uuid.UUID, user_id: uuid.UUID, member: Member, db: Database) -> None:
    require(member, "admin")
    target = member_to_manage(db, company_id, user_id)
    unassign_active_work(db, company_id, user_id)
    user = db.get(User, user_id)
    if user:
        for invitation in db.scalars(
            select(Invitation).where(
                Invitation.company_id == company_id,
                Invitation.email == user.email,
            )
        ).all():
            invitation.used = True
    db.delete(target)
    audit(db, company_id, str(member.user_id), "membership.removed", user_id)
    commit(db)


@router.post("/invitations", status_code=201)
def invite(
    company_id: uuid.UUID, req: MemberCreate, member: Member, db: Database
) -> dict[str, str]:
    require(member, "admin")
    token = secrets.token_urlsafe(32)
    invitation = Invitation(
        company_id=company_id,
        email=req.email.strip().lower(),
        role=req.role,
        token_hash=digest(token),
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    db.add(invitation)
    db.flush()
    audit(
        db, company_id, str(member.user_id), "invitation.created", invitation.id, {"role": req.role}
    )
    commit(db)
    return {
        "token": token,
        "expires_at": utc(invitation.expires_at).isoformat(),
        "note": "Share privately with the intended member. No invitation email was sent.",
    }


@router.get("/ingestion-keys")
def keys(company_id: uuid.UUID, member: Member, db: Database) -> list[dict[str, Any]]:
    require(member, "admin", "engineer")
    return [
        record(row)
        for row in db.scalars(
            select(IngestionKey).where(
                IngestionKey.company_id == company_id,
            )
        ).all()
    ]


@router.post("/ingestion-keys", status_code=201)
def create_key(
    company_id: uuid.UUID,
    member: Member,
    db: Database,
    name: str = Query(min_length=1, max_length=100),
) -> dict[str, Any]:
    require(member, "admin", "engineer")
    token = "tx_" + secrets.token_urlsafe(32)
    key = IngestionKey(company_id=company_id, name=name, token_hash=digest(token))
    db.add(key)
    db.flush()
    audit(db, company_id, str(member.user_id), "ingestion_key.created", key.id)
    commit(db)
    return {**record(key), "token": token}


@router.post("/ingestion-keys/{key_id}/revoke")
def revoke_key(
    company_id: uuid.UUID, key_id: uuid.UUID, member: Member, db: Database
) -> dict[str, Any]:
    require(member, "admin", "engineer")
    key = db.scalars(
        select(IngestionKey).where(
            IngestionKey.company_id == company_id,
            IngestionKey.id == key_id,
        )
    ).first()
    if not key:
        raise HTTPException(404, "Integration key not found")
    key.active = False
    audit(db, company_id, str(member.user_id), "ingestion_key.revoked", key_id)
    commit(db)
    return record(key)


@router.get("/audit")
def audit_events(company_id: uuid.UUID, member: Member, db: Database) -> list[dict[str, Any]]:
    require(member, *EDIT)
    return [
        record(row)
        for row in db.scalars(
            select(AuditEvent)
            .where(
                AuditEvent.company_id == company_id,
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(200)
        ).all()
    ]
