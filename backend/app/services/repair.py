"""
Repair service that orchestrates candidate generation, validation, and versioning.
"""

import pandas as pd
import numpy as np
import os
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

from app.services.dataset import DatasetService
from app.repairs.candidates import candidate_generator
from app.repairs.validation import RepairValidationService
from app.repairs.registry import get_operation, validate_operation_params

from app.repairs.versioning import versioning_service
from app.db.session import SessionLocal
from app.db.models import Dataset, DatasetVersion, QualityFinding, RepairCandidate, ValidationResult
from app.core.config import settings
from app.services.tabular_format import capture_format_metadata, read_tabular

logger = logging.getLogger(__name__)

class RepairService:
    """Service for managing the repair process."""

    def __init__(self, db_session: SessionLocal):
        self.db = db_session
        self.dataset_service = DatasetService(db_session)
        self.validation_service = RepairValidationService()
        self.candidate_generator = candidate_generator
        self.versioning_service = versioning_service

    def generate_repair_candidates(self,
                                 dataset_id: int,
                                 version_id: int,
                                 finding_id: int) -> List[Dict[str, Any]]:
        """
        Generate repair candidates for a specific quality finding.

        Args:
            dataset_id: ID of the dataset
            version_id: ID of the dataset version
            finding_id: ID of the quality finding

        Returns:
            List of candidate dictionaries ready for validation
        """
        # Get the finding
        finding = self.db.query(QualityFinding).filter(
            QualityFinding.id == finding_id,
            QualityFinding.dataset_id == dataset_id,
            QualityFinding.version_id == version_id
        ).first()

        if not finding:
            raise ValueError(f"Finding {finding_id} not found for dataset {dataset_id}, version {version_id}")

        # Get the dataset version to work with
        version = self.db.query(DatasetVersion).filter(
            DatasetVersion.id == version_id,
            DatasetVersion.dataset_id == dataset_id
        ).first()

        if not version:
            raise ValueError(f"Version {version_id} not found for dataset {dataset_id}")

        # Load the dataset
        if not os.path.exists(version.storage_path):
            raise ValueError(f"Dataset file not found: {version.storage_path}")

        df = read_tabular(version.storage_path, version.format_metadata)
        # Convert finding to dictionary for candidate generator
        finding_dict = {
            "issue_type": finding.issue_type,
            "affected_columns": finding.affected_columns or [],
            "evidence": finding.evidence or {},
            "affected_count": finding.affected_count,
            "affected_percent": finding.affected_percent
        }

        # Generate candidates
        raw_candidates = self.candidate_generator.generate_candidates_for_issue(finding_dict, df)

        # Validate and enrich candidates
        validated_candidates = []
        for i, candidate in enumerate(raw_candidates):
            operation_name = candidate.get("operation")
            parameters = candidate.get("parameters", {})

            # Validate operation parameters
            is_valid, error_msg = self.candidate_generator.validate_candidate_parameters(
                operation_name, parameters
            )

            if not is_valid and operation_name is not None:
                logger.warning(f"Invalid parameters for candidate {i}: {error_msg}")
                # Skip invalid candidates
                continue

            # Create a copy of the candidate with additional metadata
            enriched_candidate = candidate.copy()
            enriched_candidate.update({
                "candidate_id": f"cand_{dataset_id}_{version_id}_{finding_id}_{i}",
                "finding_id": finding_id,
                "dataset_id": dataset_id,
                "version_id": version_id,
                "generated_at": datetime.now().isoformat()
            })

            validated_candidates.append(enriched_candidate)

        return validated_candidates

    def validate_repair_candidate(self,
                                dataset_id: int,
                                version_id: int,
                                candidate: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a repair candidate by applying it to a copy of the dataset
        and measuring the results.

        Args:
            dataset_id: ID of the dataset
            version_id: ID of the dataset version
            candidate: Candidate dictionary from generate_repair_candidates

        Returns:
            Validation results dictionary
        """
        # Get the dataset version
        version = self.db.query(DatasetVersion).filter(
            DatasetVersion.id == version_id,
            DatasetVersion.dataset_id == dataset_id
        ).first()

        if not version:
            raise ValueError(f"Version {version_id} not found for dataset {dataset_id}")

        # Load the dataset
        if not os.path.exists(version.storage_path):
            raise ValueError(f"Dataset file not found: {version.storage_path}")

        original_df = read_tabular(version.storage_path, version.format_metadata)
        # If operation is None, it means "leave unchanged"
        operation_name = candidate.get("operation")
        parameters = candidate.get("parameters", {})

        if operation_name is None:
            # "Leave unchanged" candidate - validation is trivial
            repaired_df = original_df.copy()
        else:
            # Apply the repair operation
            try:
                operation_func = get_operation(operation_name)
                repaired_df = operation_func(original_df.copy(), parameters)
            except Exception as e:
                logger.error(f"Error applying operation {operation_name}: {str(e)}")
                # Return a failed validation result
                return {
                    "candidate_id": candidate.get("candidate_id"),
                    "operation_description": candidate.get("description", "Unknown operation"),
                    "execution_status": "failed",
                    "validation_status": "failed",
                    "metrics": {},
                    "issues_before_after": {},
                    "warnings": [],
                    "errors": [f"Failed to apply operation {operation_name}: {str(e)}"]
                }

        # Validate the repair
        issue_type = candidate.get("issue_type", "unknown")
        affected_columns = candidate.get("parameters", {}).get("columns", [])
        # For some operations, affected columns might be specified differently
        if not affected_columns and "column" in candidate.get("parameters", {}):
            affected_columns = [candidate["parameters"]["column"]]

        validation_result = self.validation_service.validate_candidate(
            original_df=original_df,
            repaired_df=repaired_df,
            operation_description=candidate.get("description", "Unknown operation"),
            issue_type=issue_type,
            affected_columns=affected_columns
        )

        # Add candidate metadata to validation result
        validation_result.update({
            "candidate_id": candidate.get("candidate_id"),
            "finding_id": candidate.get("finding_id"),
            "dataset_id": dataset_id,
            "version_id": version_id,
            "operation": operation_name,
            "parameters": parameters
        })

        return validation_result

    def save_repair_candidate(self,
                            dataset_id: int,
                            version_id: int,
                            candidate: Dict[str, Any]) -> RepairCandidate:
        """
        Save a repair candidate to the database.

        Args:
            dataset_id: ID of the dataset
            version_id: ID of the dataset version
            candidate: Candidate dictionary

        Returns:
            Saved RepairCandidate object
        """
        db_candidate = RepairCandidate(
            dataset_id=dataset_id,
            version_id=version_id,
            finding_id=candidate.get("finding_id"),
            operation=candidate.get("operation"),
            parameters=candidate.get("parameters", {}),
            description=candidate.get("description", ""),
            issue_type=candidate.get("issue_type", ""),
            candidate_id=candidate.get("candidate_id")
        )

        self.db.add(db_candidate)
        self.db.commit()
        self.db.refresh(db_candidate)
        return db_candidate

    def _json_safe(self, value):
        if isinstance(value, dict):
            return {key: self._json_safe(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [self._json_safe(item) for item in value]
        # Convert all numpy scalar types to native Python types
        if isinstance(value, (np.integer, np.int8, np.int16, np.int32, np.int64,
                              np.uint8, np.uint16, np.uint32, np.uint64)):
            return int(value)
        if isinstance(value, (np.floating, np.float16, np.float32, np.float64)):
            return float(value)
        if isinstance(value, np.bool_):
            return bool(value)
        if isinstance(value, np.ndarray):
            return value.tolist()
        if isinstance(value, (pd.Timestamp, pd.Timedelta)):
            return str(value)
        return value

    def save_validation_result(self,
                             candidate_id: int,
                             validation_result: Dict[str, Any]) -> ValidationResult:
        """
        Save a validation result to the database.

        Args:
            candidate_id: ID of the repair candidate
            validation_result: Validation results dictionary

        Returns:
            Saved ValidationResult object
        """
        db_validation = ValidationResult(
            repair_candidate_id=candidate_id,
            execution_status=validation_result.get("execution_status", "unknown"),
            validation_status=validation_result.get("validation_status", "unknown"),
            metrics=self._json_safe(validation_result.get("metrics", {})),
            issues_before_after=self._json_safe(validation_result.get("issues_before_after", {})),
            warnings=self._json_safe(validation_result.get("warnings", [])),
            errors=self._json_safe(validation_result.get("errors", [])),
            operation_description=validation_result.get("operation_description", ""),
            validated_at=datetime.now()
        )

        self.db.add(db_validation)
        self.db.commit()
        self.db.refresh(db_validation)
        return db_validation

    def approve_repair(self,
                      dataset_id: int,
                      version_id: int,
                      candidate_id: int,
                      approved_by: str = "system") -> Dict[str, Any]:
        """
        Approve a repair candidate and create a new dataset version.

        Args:
            dataset_id: ID of the dataset
            version_id: ID of the dataset version being repaired
            candidate_id: ID of the repair candidate to approve
            approved_by: Who is approving the repair

        Returns:
            Dictionary with information about the new version
        """
        # Get the candidate and its validation result
        candidate = self.db.query(RepairCandidate).filter(
            RepairCandidate.id == candidate_id,
            RepairCandidate.dataset_id == dataset_id,
            RepairCandidate.version_id == version_id
        ).first()

        if not candidate:
            raise ValueError(f"Repair candidate {candidate_id} not found")

        validation = self.db.query(ValidationResult).filter(
            ValidationResult.repair_candidate_id == candidate_id
        ).order_by(ValidationResult.id.desc()).first()

        if not validation:
            raise ValueError(f"No validation result found for candidate {candidate_id}")

        if validation.validation_status not in ["passed", "warning"]:
            raise ValueError(f"Cannot approve candidate with validation status: {validation.validation_status}")

        # Get the original dataset version
        original_version = self.db.query(DatasetVersion).filter(
            DatasetVersion.id == version_id,
            DatasetVersion.dataset_id == dataset_id
        ).first()

        if not original_version:
            raise ValueError(f"Original version {version_id} not found")

        # Load the original dataset
        if not os.path.exists(original_version.storage_path):
            raise ValueError(f"Original dataset file not found: {original_version.storage_path}")

        original_df = read_tabular(original_version.storage_path, original_version.format_metadata)
        # Determine source format metadata (may be missing for older versions)
        source_format_metadata = original_version.format_metadata or capture_format_metadata(original_version.storage_path)

        # Apply the repair operation
        operation_name = candidate.operation
        parameters = candidate.parameters or {}

        if operation_name is None:
            # "Leave unchanged" - just copy the original
            repaired_df = original_df.copy()
        else:
            try:
                operation_func = get_operation(operation_name)
                repaired_df = operation_func(original_df.copy(), parameters)
            except Exception as e:
                raise ValueError(f"Failed to apply repair operation {operation_name}: {str(e)}")

        # Save as a new version
        version_info = self.versioning_service.save_version(
            df=repaired_df,
            dataset_id=dataset_id,
            parent_version_id=version_id,
            version_type="repaired",
            description=f"Repair approved: {candidate.description}",
            format_metadata=source_format_metadata
        )

        # Create the new dataset version record
        new_version = DatasetVersion(
            dataset_id=dataset_id,
            version_number=self._get_next_version_number(dataset_id),
            storage_path=version_info["storage_path"],
            version_type="repaired",
            content_hash=version_info["content_hash"],
            parent_version_id=version_id,
            created_by=approved_by,
            file_format=version_info.get("file_format"),
            format_metadata=version_info.get("format_metadata"),
            artifact_status="committed"
        )

        self.db.add(new_version)
        self.db.commit()
        self.db.refresh(new_version)

        # Create audit event
        from app.db.models import AuditEvent
        audit_event = AuditEvent(
            dataset_id=dataset_id,
            event_type="approve",
            event_data={
                "candidate_id": candidate_id,
                "operation": operation_name,
                "parameters": parameters,
                "validation_status": validation.validation_status,
                "new_version_id": new_version.id,
                "approved_by": approved_by
            },
            performed_by=approved_by
        )
        self.db.add(audit_event)
        self.db.commit()

        return {
            "new_version_id": new_version.id,
            "version_number": new_version.version_number,
            "storage_path": new_version.storage_path,
            "content_hash": new_version.content_hash,
            "approved_by": approved_by,
            "approved_at": new_version.created_at.isoformat(),
            "file_format": new_version.file_format
        }

    def reject_repair(self,
                     dataset_id: int,
                     version_id: int,
                     candidate_id: int,
                     rejected_by: str = "system") -> Dict[str, Any]:
        """
        Reject a repair candidate.

        Args:
            dataset_id: ID of the dataset
            version_id: ID of the dataset version
            candidate_id: ID of the repair candidate to reject
            rejected_by: Who is rejecting the repair

        Returns:
            Dictionary with rejection information
        """
        # Verify the candidate exists
        candidate = self.db.query(RepairCandidate).filter(
            RepairCandidate.id == candidate_id,
            RepairCandidate.dataset_id == dataset_id,
            RepairCandidate.version_id == version_id
        ).first()

        if not candidate:
            raise ValueError(f"Repair candidate {candidate_id} not found")

        # Create audit event for rejection
        from app.db.models import AuditEvent
        audit_event = AuditEvent(
            dataset_id=dataset_id,
            event_type="reject",
            event_data={
                "candidate_id": candidate_id,
                "operation": candidate.operation,
                "parameters": candidate.parameters,
                "rejected_by": rejected_by
            },
            performed_by=rejected_by
        )
        self.db.add(audit_event)
        self.db.commit()

        return {
            "candidate_id": candidate_id,
            "rejected_by": rejected_by,
            "rejected_at": datetime.now().isoformat()
        }

    def rollback_to_version(self,
                           dataset_id: int,
                           target_version_id: int,
                           rolled_back_by: str = "system") -> Dict[str, Any]:
        """
        Rollback the dataset to a previous version.

        Args:
            dataset_id: ID of the dataset
            target_version_id: ID of the version to rollback to
            rolled_back_by: Who is performing the rollback

        Returns:
            Dictionary with rollback information
        """
        # Verify the target version exists and belongs to the dataset
        target_version = self.db.query(DatasetVersion).filter(
            DatasetVersion.id == target_version_id,
            DatasetVersion.dataset_id == dataset_id
        ).first()

        if not target_version:
            raise ValueError(f"Target version {target_version_id} not found for dataset {dataset_id}")

        # Verify the target version file exists
        if not os.path.exists(target_version.storage_path):
            raise ValueError(f"Target version file not found: {target_version.storage_path}")

        # Get the current latest version
        current_version = self.db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == dataset_id
        ).order_by(DatasetVersion.version_number.desc()).first()

        if not current_version:
            raise ValueError(f"No current version found for dataset {dataset_id}")

        # Create a new version that is a copy of the target version (for rollback tracking)
        # We'll copy the target version file to a new location to represent the rollback
        target_format_metadata = target_version.format_metadata or capture_format_metadata(target_version.storage_path)
        rollback_df = read_tabular(target_version.storage_path, target_format_metadata)
        rollback_version_info = self.versioning_service.save_version(
            df=rollback_df,
            dataset_id=dataset_id,
            parent_version_id=current_version.id,
            version_type="rolled_back",
            description=f"Rollback to version {target_version.version_number}",
            format_metadata=target_format_metadata
        )

        # Create the rollback version record
        rollback_version = DatasetVersion(
            dataset_id=dataset_id,
            version_number=self._get_next_version_number(dataset_id),
            storage_path=rollback_version_info["storage_path"],
            version_type="rolled_back",
            content_hash=rollback_version_info["content_hash"],
            parent_version_id=current_version.id,
            created_by=rolled_back_by,
            file_format=rollback_version_info.get("file_format"),
            format_metadata=rollback_version_info.get("format_metadata"),
            artifact_status="committed"
        )

        self.db.add(rollback_version)
        self.db.commit()
        self.db.refresh(rollback_version)

        # Create audit event
        from app.db.models import AuditEvent
        audit_event = AuditEvent(
            dataset_id=dataset_id,
            event_type="rollback",
            event_data={
                "target_version_id": target_version_id,
                "target_version_number": target_version.version_number,
                "rollback_version_id": rollback_version.id,
                "rolled_back_by": rolled_back_by
            },
            performed_by=rolled_back_by
        )
        self.db.add(audit_event)
        self.db.commit()

        return {
            "rollback_version_id": rollback_version.id,
            "version_number": rollback_version.version_number,
            "storage_path": rollback_version.storage_path,
            "content_hash": rollback_version.content_hash,
            "rolled_back_to_version": target_version.version_number,
            "rolled_back_by": rolled_back_by,
            "rolled_back_at": rollback_version.created_at.isoformat(),
            "file_format": rollback_version.file_format
        }

    def get_repair_history(self, dataset_id: int) -> List[Dict[str, Any]]:
        """
        Get the repair history for a dataset.

        Args:
            dataset_id: ID of the dataset

        Returns:
            List of repair history entries
        """
        # Get all audit events for approve, reject, rollback operations
        from app.db.models import AuditEvent
        events = self.db.query(AuditEvent).filter(
            AuditEvent.dataset_id == dataset_id,
            AuditEvent.event_type.in_(["approve", "reject", "rollback"])
        ).order_by(AuditEvent.performed_at.desc()).all()

        history = []
        for event in events:
            history.append({
                "id": event.id,
                "event_type": event.event_type,
                "performed_by": event.performed_by,
                "performed_at": event.performed_at.isoformat() if event.performed_at else None,
                "event_data": event.event_data
            })

        return history

    def _read_tabular(self, path: str, format_metadata: Optional[Dict[str, Any]] = None):
        return read_tabular(path, format_metadata)

    def _get_next_version_number(self, dataset_id: int) -> int:
        """Get the next version number for a dataset."""
        latest_version = self.db.query(DatasetVersion).filter(
            DatasetVersion.dataset_id == dataset_id
        ).order_by(DatasetVersion.version_number.desc()).first()

        if latest_version:
            return latest_version.version_number + 1
        else:
            return 1

# Factory function to create RepairService instances
def get_repair_service(db_session: SessionLocal) -> RepairService:
    """Factory function to create a RepairService instance."""
    return RepairService(db_session)