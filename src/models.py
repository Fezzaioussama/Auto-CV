"""Database models for Auto-CV.

The data model is built around per-user ownership so the app is multi-tenant
safe: every row a request can read or write hangs off a ``user_id`` that must
match ``current_user``. Helper query methods enforce that scoping in one place.

Entities
--------
* ``User``        — an account (email + password hash).
* ``Job``         — a saved job offer (raw text + parsed analysis JSON).
* ``CVDocument``  — a named CV owned by a user (the "master" record).
* ``CVVersion``   — an immutable snapshot of a CV's LaTeX, optionally tied to the
                    job it was tailored for. This is the version history.
* ``CoverLetter`` — generated outreach text (cover letter / recruiter / email…).
"""

from __future__ import annotations

from datetime import datetime

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

try:  # importable both as a bare module (main.py) and as the src package
    from extensions import db, login_manager
except ImportError:  # pragma: no cover
    from .extensions import db, login_manager


def _utcnow() -> datetime:
    return datetime.utcnow()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    # Email confirmation. Login is allowed while unverified unless
    # REQUIRE_EMAIL_VERIFICATION is on; the UI nudges the user to confirm.
    email_verified = db.Column(db.Boolean, default=False, nullable=False)
    verified_at = db.Column(db.DateTime, nullable=True)

    jobs = db.relationship("Job", backref="user", lazy=True, cascade="all, delete-orphan")
    cvs = db.relationship("CVDocument", backref="user", lazy=True, cascade="all, delete-orphan")
    cover_letters = db.relationship(
        "CoverLetter", backref="user", lazy=True, cascade="all, delete-orphan"
    )

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "email_verified": self.email_verified,
        }


@login_manager.user_loader
def load_user(user_id: str):  # noqa: D401 - Flask-Login callback
    return db.session.get(User, int(user_id)) if user_id else None


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(255), nullable=True)
    company = db.Column(db.String(255), nullable=True)
    raw_text = db.Column(db.Text, nullable=False)
    # Parsed output from parser.py (skills/requirements/qualifications/sections).
    parsed = db.Column(db.JSON, nullable=True)
    language = db.Column(db.String(8), default="en", nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    # --- Application tracking -------------------------------------------
    # Where this application stands, so the workspace is a tracker, not just a
    # list. One of: saved | applied | interviewing | offer | rejected.
    status = db.Column(db.String(16), default="saved", nullable=False)
    applied_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)
    url = db.Column(db.String(1024), nullable=True)

    cv_versions = db.relationship("CVVersion", backref="job", lazy=True)
    cover_letters = db.relationship("CoverLetter", backref="job", lazy=True)

    def to_dict(self, *, include_text: bool = False) -> dict:
        data = {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "language": self.language,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "skills": (self.parsed or {}).get("skills", []),
            "status": self.status,
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
            "url": self.url,
            "notes": self.notes,
        }
        if include_text:
            data["raw_text"] = self.raw_text
            data["parsed"] = self.parsed
        return data


class CVDocument(db.Model):
    __tablename__ = "cv_documents"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False, default="My CV")
    # Where the original came from: 'latex' | 'pdf' | 'docx' | 'text'.
    source_format = db.Column(db.String(16), default="latex", nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow, nullable=False)

    versions = db.relationship(
        "CVVersion",
        backref="document",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="CVVersion.created_at.desc()",
    )

    def to_dict(self, *, include_versions: bool = False) -> dict:
        data = {
            "id": self.id,
            "name": self.name,
            "source_format": self.source_format,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "version_count": len(self.versions),
        }
        if include_versions:
            data["versions"] = [v.to_dict() for v in self.versions]
        return data


class CVVersion(db.Model):
    __tablename__ = "cv_versions"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer, db.ForeignKey("cv_documents.id"), nullable=False, index=True
    )
    # The job this version was tailored for (optional — e.g. the original upload).
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=True, index=True)
    label = db.Column(db.String(255), nullable=True)
    latex = db.Column(db.Text, nullable=False)
    # Snapshot of the match analysis at the time this version was saved.
    analysis = db.Column(db.JSON, nullable=True)
    template = db.Column(db.String(64), nullable=True)
    language = db.Column(db.String(8), default="en", nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    def to_dict(self, *, include_latex: bool = False) -> dict:
        data = {
            "id": self.id,
            "document_id": self.document_id,
            "job_id": self.job_id,
            "label": self.label,
            "template": self.template,
            "language": self.language,
            "score": (self.analysis or {}).get("overall_score"),
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
        if include_latex:
            data["latex"] = self.latex
            data["analysis"] = self.analysis
        return data


class CoverLetter(db.Model):
    __tablename__ = "cover_letters"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey("jobs.id"), nullable=True, index=True)
    cv_version_id = db.Column(db.Integer, db.ForeignKey("cv_versions.id"), nullable=True)
    # 'cover_letter' | 'recruiter_message' | 'linkedin_message' | 'email'
    kind = db.Column(db.String(32), default="cover_letter", nullable=False)
    content = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(8), default="en", nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "job_id": self.job_id,
            "cv_version_id": self.cv_version_id,
            "kind": self.kind,
            "content": self.content,
            "language": self.language,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
