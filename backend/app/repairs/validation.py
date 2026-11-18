"""
Validation service for repair candidates.
Runs repair operations on dataset copies and evaluates results against validation metrics.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from scipy import stats
import math

class RepairValidationService:
    """Service for validating repair candidates."""

    def __init__(self):
        # Business rules for validation (can be configured)
        self.business_rules = {
            "non_negative": ["quantity", "amount", "price", "salary", "age"],
            "date_order": [("start_date", "end_date"), ("effective_date", "expiration_date")],
            "required_fields": [],  # To be configured per dataset
            "value_ranges": {
                "age": (0, 120),
                "temperature": (-50, 150),
                "percentage": (0, 100)
            }
        }

    def validate_candidate(self,
                          original_df: pd.DataFrame,
                          repaired_df: pd.DataFrame,
                          operation_description: str,
                          issue_type: str,
                          affected_columns: List[str]) -> Dict[str, Any]:
        """
        Validate a repair candidate by comparing original vs repaired dataset.

        Returns:
            Dict with validation results including:
            - execution_status: "executed" (always true if we got here)
            - validation_status: "passed", "failed", or "warning"
            - metrics: Dictionary of validation metrics
            - issues_before_after: Count of specific issues before/after repair
        """
        validation_result = {
            "operation_description": operation_description,
            "execution_status": "executed",
            "validation_status": "pending",
            "metrics": {},
            "issues_before_after": {},
            "warnings": [],
            "errors": []
        }

        try:
            # Basic dataset metrics
            validation_result["metrics"]["row_count_change"] = len(repaired_df) - len(original_df)
            validation_result["metrics"]["row_count_percent_change"] = (
                (len(repaired_df) - len(original_df)) / len(original_df) * 100
                if len(original_df) > 0 else 0
            )
            validation_result["metrics"]["column_count_change"] = len(repaired_df.columns) - len(original_df.columns)

            # Check for data loss/gain
            if len(repaired_df) < len(original_df):
                validation_result["warnings"].append(
                    f"Row count decreased by {len(original_df) - len(repaired_df)} rows "
                    f"({validation_result['metrics']['row_count_percent_change']:.2f}%)"
                )

            # Column changes
            added_cols = set(repaired_df.columns) - set(original_df.columns)
            removed_cols = set(original_df.columns) - set(repaired_df.columns)
            if added_cols:
                validation_result["metrics"]["added_columns"] = list(added_cols)
                validation_result["warnings"].append(f"Added columns: {list(added_cols)}")
            if removed_cols:
                validation_result["metrics"]["removed_columns"] = list(removed_cols)
                validation_result["warnings"].append(f"Removed columns: {list(removed_cols)}")

            # Validate data types are preserved (no unexpected type changes)
            type_changes = []
            for col in original_df.columns:
                if col in repaired_df.columns:
                    orig_type = str(original_df[col].dtype)
                    repair_type = str(repaired_df[col].dtype)
                    if orig_type != repair_type:
                        type_changes.append({
                            "column": col,
                            "original_type": orig_type,
                            "repaired_type": repair_type
                        })

            if type_changes:
                validation_result["metrics"]["type_changes"] = type_changes
                validation_result["warnings"].append(
                    f"Data type changes detected in {len(type_changes)} columns"
                )

            # Issue-specific validation: count specific issues before/after
            if issue_type == "missing_values":
                validation_result["issues_before_after"] = self._validate_missing_values_fix(
                    original_df, repaired_df, affected_columns
                )
            elif issue_type == "duplicate_rows":
                validation_result["issues_before_after"] = self._validate_duplicates_fix(
                    original_df, repaired_df
                )
            elif issue_type == "negative_values":
                validation_result["issues_before_after"] = self._validate_negative_values_fix(
                    original_df, repaired_df, affected_columns
                )
            elif issue_type == "out_of_range_numbers":
                validation_result["issues_before_after"] = self._validate_out_of_range_fix(
                    original_df, repaired_df, affected_columns
                )
            elif issue_type == "invalid_dates":
                validation_result["issues_before_after"] = self._validate_invalid_dates_fix(
                    original_df, repaired_df, affected_columns
                )
            elif issue_type == "category_variants":
                validation_result["issues_before_after"] = self._validate_category_variants_fix(
                    original_df, repaired_df, affected_columns
                )
            else:
                # Generic validation for other issue types
                validation_result["issues_before_after"] = self._validate_generic_fix(
                    original_df, repaired_df, affected_columns
                )

            # Business rule validation
            business_rule_violations = self._validate_business_rules(
                original_df, repaired_df
            )
            validation_result["metrics"]["business_rule_violations"] = business_rule_violations

            # Distribution validation for numeric columns
            if affected_columns:
                numeric_cols = [col for col in affected_columns
                              if col in original_df.columns and
                                 pd.api.types.is_numeric_dtype(original_df[col])]
                if numeric_cols:
                    dist_changes = self._validate_distribution_changes(
                        original_df, repaired_df, numeric_cols
                    )
                    validation_result["metrics"]["distribution_changes"] = dist_changes

            # Determine overall validation status
            validation_result["validation_status"] = self._determine_validation_status(
                validation_result
            )

        except Exception as e:
            validation_result["validation_status"] = "error"
            validation_result["errors"].append(f"Validation error: {str(e)}")

        return validation_result

    def _validate_missing_values_fix(self,
                                   original_df: pd.DataFrame,
                                   repaired_df: pd.DataFrame,
                                   affected_columns: List[str]) -> Dict[str, Any]:
        """Validate missing values repair."""
        result = {}
        for col in affected_columns:
            if col in original_df.columns and col in repaired_df.columns:
                orig_missing = original_df[col].isna().sum()
                repair_missing = repaired_df[col].isna().sum()
                result[col] = {
                    "missing_before": int(orig_missing),
                    "missing_after": int(repair_missing),
                    "fixed": int(orig_missing - repair_missing),
                    "percent_fixed": (
                        (orig_missing - repair_missing) / orig_missing * 100
                        if orig_missing > 0 else 0
                    )
                }
        return result

    def _validate_duplicates_fix(self,
                               original_df: pd.DataFrame,
                               repaired_df: pd.DataFrame) -> Dict[str, Any]:
        """Validate duplicate removal."""
        orig_duplicates = original_df.duplicated().sum()
        repair_duplicates = repaired_df.duplicated().sum()

        return {
            "duplicate_rows": {
                "duplicates_before": int(orig_duplicates),
                "duplicates_after": int(repair_duplicates),
                "removed": int(orig_duplicates - repair_duplicates),
                "percent_removed": (
                    (orig_duplicates - repair_duplicates) / orig_duplicates * 100
                    if orig_duplicates > 0 else 0
                )
            }
        }

    def _validate_negative_values_fix(self,
                                    original_df: pd.DataFrame,
                                    repaired_df: pd.DataFrame,
                                    affected_columns: List[str]) -> Dict[str, Any]:
        """Validate negative values repair."""
        result = {}
        for col in affected_columns:
            if col in original_df.columns and col in repaired_df.columns:
                orig_negative = (original_df[col] < 0).sum()
                repair_negative = (repaired_df[col] < 0).sum()
                result[col] = {
                    "negative_before": int(orig_negative),
                    "negative_after": int(repair_negative),
                    "fixed": int(orig_negative - repair_negative),
                    "percent_fixed": (
                        (orig_negative - repair_negative) / orig_negative * 100
                        if orig_negative > 0 else 0
                    )
                }
        return result

    def _validate_out_of_range_fix(self,
                                 original_df: pd.DataFrame,
                                 repaired_df: pd.DataFrame,
                                 affected_columns: List[str]) -> Dict[str, Any]:
        """Validate out-of-range numbers repair."""
        result = {}
        for col in affected_columns:
            if col not in original_df.columns or col not in repaired_df.columns:
                continue

            # Get configured range for this column
            min_val, max_val = self.business_rules["value_ranges"].get(col, (None, None))
            if min_val is None and max_val is None:
                # No specific range configured, skip
                continue

            orig_out_of_range = 0
            repair_out_of_range = 0

            if min_val is not None:
                orig_out_of_range += (original_df[col] < min_val).sum()
                repair_out_of_range += (repaired_df[col] < min_val).sum()
            if max_val is not None:
                orig_out_of_range += (original_df[col] > max_val).sum()
                repair_out_of_range += (repaired_df[col] > max_val).sum()

            result[col] = {
                "out_of_range_before": int(orig_out_of_range),
                "out_of_range_after": int(repair_out_of_range),
                "fixed": int(orig_out_of_range - repair_out_of_range),
                "percent_fixed": (
                    (orig_out_of_range - repair_out_of_range) / orig_out_of_range * 100
                    if orig_out_of_range > 0 else 0
                ),
                "valid_range": [min_val, max_val]
            }
        return result

    def _validate_invalid_dates_fix(self,
                                  original_df: pd.DataFrame,
                                  repaired_df: pd.DataFrame,
                                  affected_columns: List[str]) -> Dict[str, Any]:
        """Validate invalid dates repair."""
        result = {}
        for col in affected_columns:
            if col not in original_df.columns or col not in repaired_df.columns:
                continue

            # Count invalid/unparseable dates
            orig_invalid = pd.to_datetime(original_df[col], errors='coerce').isna().sum()
            repair_invalid = pd.to_datetime(repaired_df[col], errors='coerce').isna().sum()

            result[col] = {
                "invalid_dates_before": int(orig_invalid),
                "invalid_dates_after": int(repair_invalid),
                "fixed": int(orig_invalid - repair_invalid),
                "percent_fixed": (
                    (orig_invalid - repair_invalid) / orig_invalid * 100
                    if orig_invalid > 0 else 0
                )
            }
        return result

    def _validate_category_variants_fix(self,
                                      original_df: pd.DataFrame,
                                      repaired_df: pd.DataFrame,
                                      affected_columns: List[str]) -> Dict[str, Any]:
        """Validate category variants repair."""
        result = {}
        for col in affected_columns:
            if col not in original_df.columns or col not in repaired_df.columns:
                continue

            # Count unique values (after stripping and lowercasing for comparison)
            orig_series = original_df[col].dropna().astype(str).str.strip()
            repair_series = repaired_df[col].dropna().astype(str).str.strip()

            orig_unique_count = orig_series.nunique()
            repair_unique_count = repair_series.nunique()

            result[col] = {
                "unique_values_before": int(orig_unique_count),
                "unique_values_after": int(repair_unique_count),
                "reduced_by": int(orig_unique_count - repair_unique_count),
                "percent_reduced": (
                    (orig_unique_count - repair_unique_count) / orig_unique_count * 100
                    if orig_unique_count > 0 else 0
                )
            }
        return result

    def _validate_generic_fix(self,
                            original_df: pd.DataFrame,
                            repaired_df: pd.DataFrame,
                            affected_columns: List[str]) -> Dict[str, Any]:
        """Generic validation for unspecified issue types."""
        result = {}
        for col in affected_columns:
            if col in original_df.columns and col in repaired_df.columns:
                # Simple comparison: count of null values and unique values
                orig_null = original_df[col].isna().sum()
                repair_null = repaired_df[col].isna().sum()
                orig_unique = original_df[col].nunique()
                repair_unique = repaired_df[col].nunique()

                result[col] = {
                    "null_values_before": int(orig_null),
                    "null_values_after": int(repair_null),
                    "unique_values_before": int(orig_unique),
                    "unique_values_after": int(repair_unique)
                }
        return result

    def _validate_business_rules(self,
                               original_df: pd.DataFrame,
                               repaired_df: pd.DataFrame) -> Dict[str, Any]:
        """Validate business rule compliance."""
        violations = {"original": {}, "repaired": {}}

        # Non-negative values check
        for col in self.business_rules["non_negative"]:
            if col in original_df.columns:
                orig_neg = (original_df[col] < 0).sum()
                violations["original"][f"{col}_negative"] = int(orig_neg)
            if col in repaired_df.columns:
                repair_neg = (repaired_df[col] < 0).sum()
                violations["repaired"][f"{col}_negative"] = int(repair_neg)

        # Date order checks
        for date_pair in self.business_rules["date_order"]:
            start_col, end_col = date_pair
            if start_col in original_df.columns and end_col in original_df.columns:
                try:
                    start_dates = pd.to_datetime(original_df[start_col], errors='coerce')
                    end_dates = pd.to_datetime(original_df[end_col], errors='coerce')
                    invalid_order = (end_dates < start_dates) & start_dates.notna() & end_dates.notna()
                    violations["original"][f"{start_col}_{end_col}_order"] = int(invalid_order.sum())
                except Exception:
                    pass

            if start_col in repaired_df.columns and end_col in repaired_df.columns:
                try:
                    start_dates = pd.to_datetime(repaired_df[start_col], errors='coerce')
                    end_dates = pd.to_datetime(repaired_df[end_col], errors='coerce')
                    invalid_order = (end_dates < start_dates) & start_dates.notna() & end_dates.notna()
                    violations["repaired"][f"{start_col}_{end_col}_order"] = int(invalid_order.sum())
                except Exception:
                    pass

        # Value range checks
        for col, (min_val, max_val) in self.business_rules["value_ranges"].items():
            if col in original_df.columns:
                if min_val is not None:
                    orig_below_min = (original_df[col] < min_val).sum()
                    violations["original"][f"{col}_below_min"] = int(orig_below_min)
                if max_val is not None:
                    orig_above_max = (original_df[col] > max_val).sum()
                    violations["original"][f"{col}_above_max"] = int(orig_above_max)

            if col in repaired_df.columns:
                if min_val is not None:
                    repair_below_min = (repaired_df[col] < min_val).sum()
                    violations["repaired"][f"{col}_below_min"] = int(repair_below_min)
                if max_val is not None:
                    repair_above_max = (repaired_df[col] > max_val).sum()
                    violations["repaired"][f"{col}_above_max"] = int(repair_above_max)

        return violations

    def _validate_distribution_changes(self,
                                     original_df: pd.DataFrame,
                                     repaired_df: pd.DataFrame,
                                     numeric_columns: List[str]) -> Dict[str, Any]:
        """Validate distribution changes for numeric columns."""
        changes = {}

        for col in numeric_columns:
            if col not in original_df.columns or col not in repaired_df.columns:
                continue

            orig_vals = original_df[col].dropna()
            repair_vals = repaired_df[col].dropna()

            if len(orig_vals) == 0 or len(repair_vals) == 0:
                continue

            # Basic statistics
            orig_mean = float(orig_vals.mean())
            repair_mean = float(repair_vals.mean())
            orig_std = float(orig_vals.std())
            repair_std = float(repair_vals.std())
            orig_median = float(orig_vals.median())
            repair_median = float(repair_vals.median())

            # Kolmogorov-Smirnov test for distribution similarity
            try:
                ks_stat, ks_pvalue = stats.ks_2samp(orig_vals, repair_vals)
                ks_test = {
                    "statistic": float(ks_stat),
                    "p_value": float(ks_pvalue),
                    "significant_difference": ks_pvalue < 0.05  # Significant if p < 0.05
                }
            except Exception:
                ks_test = {"error": "Could not compute KS test"}

            changes[col] = {
                "mean_change": {
                    "before": orig_mean,
                    "after": repair_mean,
                    "absolute_change": repair_mean - orig_mean,
                    "percent_change": ((repair_mean - orig_mean) / orig_mean * 100) if orig_mean != 0 else 0
                },
                "std_change": {
                    "before": orig_std,
                    "after": repair_std,
                    "absolute_change": repair_std - orig_std,
                    "percent_change": ((repair_std - orig_std) / orig_std * 100) if orig_std != 0 else 0
                },
                "median_change": {
                    "before": orig_median,
                    "after": repair_median,
                    "absolute_change": repair_median - orig_median,
                    "percent_change": ((repair_median - orig_median) / orig_median * 100) if orig_median != 0 else 0
                },
                "ks_test": ks_test,
                "sample_size": {
                    "before": int(len(orig_vals)),
                    "after": int(len(repair_vals))
                }
            }

        return changes

    def _determine_validation_status(self, validation_result: Dict[str, Any]) -> str:
        """Determine overall validation status based on results."""
        # If there are errors, validation failed
        if validation_result["errors"]:
            return "failed"

        # Check for critical issues that would cause failure
        critical_failures = []

        # 1. Data loss without justification (more than 5% row loss)
        row_loss = validation_result["metrics"].get("row_count_percent_change", 0)
        if row_loss < -5:  # More than 5% loss
            critical_failures.append(f"Excessive row loss: {abs(row_loss):.2f}%")

        # 2. Too many column removals
        removed_cols = validation_result["metrics"].get("removed_columns", [])
        if len(removed_cols) > 0:
            critical_failures.append(f"Columns removed: {removed_cols}")

        # 3. Business rule violations in repaired data (only fail if NEW violations introduced)
        repaired_violations = validation_result["metrics"].get("business_rule_violations", {}).get("repaired", {})
        original_violations = validation_result["metrics"].get("business_rule_violations", {}).get("original", {})
        total_repaired_violations = sum(repaired_violations.values())
        total_original_violations = sum(original_violations.values())
        new_violations = total_repaired_violations - total_original_violations
        if new_violations > 0:
            critical_failures.append(f"New business rule violations introduced by repair: {new_violations}")

        # 4. Significant negative impact on data quality (more issues after repair)
        # This is handled in the Repair Tournament comparison logic

        if critical_failures:
            validation_result["warnings"].extend(critical_failures)
            return "failed"

        # If we have warnings but no critical failures, it's a warning status
        if validation_result["warnings"]:
            return "warning"

        # Otherwise, passed
        return "passed"