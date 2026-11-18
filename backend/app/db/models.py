from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Float, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    versions = relationship("DatasetVersion", back_populates="dataset")
    profiles = relationship("DatasetProfile", back_populates="dataset")
    findings = relationship("QualityFinding", back_populates="dataset")
    audit_events = relationship("AuditEvent", back_populates="dataset")
    repair_candidates = relationship("RepairCandidate", back_populates="dataset")

class DatasetVersion(Base):
    __tablename__ = "dataset_versions"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"))
    version_number = Column(Integer)
    storage_path = Column(String)
    version_type = Column(String)  # original, repaired, rolled_back
    content_hash = Column(String)
    parent_version_id = Column(Integer, ForeignKey("dataset_versions.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String, default="system")
    file_format = Column(String, nullable=True)
    format_metadata = Column(JSON, nullable=True)
    artifact_status = Column(String, default="committed")

    # Relationships
    dataset = relationship("Dataset", back_populates="versions")
    parent = relationship("DatasetVersion", remote_side=[id])
    profiles = relationship("DatasetProfile", back_populates="version")
    findings = relationship("QualityFinding", back_populates="version")
    repair_candidates = relationship("RepairCandidate", back_populates="version")

class DatasetProfile(Base):
    __tablename__ = "dataset_profiles"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"))
    version_id = Column(Integer, ForeignKey("dataset_versions.id"))
    profile_data = Column(JSON)  # Store profiling results as JSON
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    dataset = relationship("Dataset", back_populates="profiles")
    version = relationship("DatasetVersion", back_populates="profiles")

class QualityFinding(Base):
    __tablename__ = "quality_findings"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"))
    version_id = Column(Integer, ForeignKey("dataset_versions.id"))
    finding_id = Column(String, index=True)  # Unique identifier for the finding type
    issue_type = Column(String)  # missing_values, duplicate_rows, etc.
    severity = Column(String)  # low, medium, high, critical
    affected_columns = Column(JSON)  # List of column names
    affected_count = Column(Integer)
    affected_percent = Column(Float)
    evidence = Column(JSON)  # Examples, row IDs, etc.
    possible_causes = Column(JSON, nullable=True)
    recommended_next_action = Column(String)
    validation_status = Column(String, default="pending")  # pending, validated, rejected
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    dataset = relationship("Dataset", back_populates="findings")
    version = relationship("DatasetVersion", back_populates="findings")
    repair_candidates = relationship("RepairCandidate", back_populates="finding")

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"))
    event_type = Column(String)  # upload, analyze, approve, reject, rollback
    event_data = Column(JSON)  # Details of the event
    performed_by = Column(String, default="system")
    performed_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    dataset = relationship("Dataset", back_populates="audit_events")

class RepairCandidate(Base):
    __tablename__ = "repair_candidates"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"))
    version_id = Column(Integer, ForeignKey("dataset_versions.id"))
    finding_id = Column(Integer, ForeignKey("quality_findings.id"))
    operation = Column(String, nullable=True)  # Name of the operation, or None for "leave unchanged"
    parameters = Column(JSON)  # Parameters for the operation
    description = Column(Text)  # Human-readable description
    issue_type = Column(String)  # Type of issue this candidate addresses
    candidate_id = Column(String, index=True)  # Unique identifier for the candidate
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    dataset = relationship("Dataset", back_populates="repair_candidates")
    version = relationship("DatasetVersion", back_populates="repair_candidates")
    finding = relationship("QualityFinding", back_populates="repair_candidates")
    validation_results = relationship("ValidationResult", back_populates="repair_candidate")

class ValidationResult(Base):
    __tablename__ = "validation_results"

    id = Column(Integer, primary_key=True, index=True)
    repair_candidate_id = Column(Integer, ForeignKey("repair_candidates.id"))
    execution_status = Column(String)  # executed, failed
    validation_status = Column(String)  # passed, failed, warning, error
    metrics = Column(JSON)  # Validation metrics
    issues_before_after = Column(JSON)  # Issue counts before/after repair
    warnings = Column(JSON)  # List of warning messages
    errors = Column(JSON)  # List of error messages
    operation_description = Column(Text)  # Description of the operation that was validated
    validated_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    repair_candidate = relationship("RepairCandidate", back_populates="validation_results")