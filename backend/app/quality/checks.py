import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional
from datetime import datetime
import re

class QualityCheckService:
    def __init__(self):
        # Business rules can be configured
        self.business_rules = {
            "non_negative": ["quantity", "amount", "price", "salary", "age"],
            "date_order": [("start_date", "end_date"), ("effective_date", "expiration_date")],
            "required_fields": [],  # To be configured per dataset
            "unique_combinations": [],  # To be configured per dataset
            "value_ranges": {
                "age": (0, 120),
                "temperature": (-50, 150),
                "percentage": (0, 100)
            }
        }

    def run_all_checks(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Run all quality checks on a DataFrame and return findings.
        """
        findings = []

        # Missing values check
        findings.extend(self._check_missing_values(df))

        # Duplicate rows check
        findings.extend(self._check_duplicate_rows(df))

        # Type problems check
        findings.extend(self._check_type_problems(df))

        # Invalid dates and mixed date formats
        findings.extend(self._check_date_issues(df))

        # Category spelling, case and whitespace variants
        findings.extend(self._check_category_issues(df))

        # Out-of-range numbers
        findings.extend(self._check_out_of_range_numbers(df))

        # Business rule violations
        findings.extend(self._check_business_rules(df))

        # Contradictory field combinations
        findings.extend(self._check_contradictory_fields(df))

        return findings

    def _check_missing_values(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Check for missing values in each column."""
        findings = []
        for column in df.columns:
            missing_count = df[column].isnull().sum()
            if missing_count > 0:
                missing_percent = (missing_count / len(df)) * 100
                # Get example row indices (up to 5)
                example_rows = df[df[column].isnull()].index[:5].tolist()

                findings.append({
                    "finding_id": f"missing_values_{column}_{hash(str(df[column].isnull()))}",
                    "issue_type": "missing_values",
                    "severity": self._get_severity_from_percent(missing_percent),
                    "affected_columns": [column],
                    "affected_count": int(missing_count),
                    "affected_percent": round(missing_percent, 2),
                    "evidence": {
                        "description": f"Column '{column}' has {missing_count} missing values ({missing_percent:.2f}%)",
                        "example_row_indices": example_rows,
                        "example_values": df.loc[example_rows, column].fillna("NULL").tolist() if len(example_rows) > 0 else []
                    },
                    "possible_causes": [],  # To be filled by AI later
                    "recommended_next_action": "Consider imputation or investigation of missing data mechanism",
                    "validation_status": "pending"
                })
        return findings

    def _check_duplicate_rows(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Check for duplicate rows."""
        findings = []
        duplicate_mask = df.duplicated(keep=False)
        duplicate_count = duplicate_mask.sum()

        if duplicate_count > 0:
            # Get groups of duplicates
            duplicated_df = df[duplicate_mask]
            duplicate_groups = duplicated_df.groupby(list(df.columns)).groups

            # For each group, we'll show examples
            example_groups = list(duplicate_groups.values())[:3]  # Show up to 3 groups
            example_rows = []
            for group_indices in example_groups:
                example_rows.extend(list(group_indices)[:2])  # Up to 2 rows per group

            findings.append({
                "finding_id": f"duplicate_rows_{hash(str(duplicate_mask))}",
                "issue_type": "duplicate_rows",
                "severity": "medium" if duplicate_count < len(df) * 0.1 else "high",
                "affected_columns": list(df.columns),
                "affected_count": int(duplicate_count),
                "affected_percent": round((duplicate_count / len(df)) * 100, 2),
                "evidence": {
                    "description": f"Found {duplicate_count} duplicate rows ({duplicate_count/len(df)*100:.2f}%)",
                    "example_row_indices": example_rows[:10],  # Limit to 10 examples
                    "example_rows": df.loc[example_rows[:10]].to_dict('records') if len(example_rows) > 0 else []
                },
                "possible_causes": ["Data entry errors", "System integration issues", "Batch processing duplicates"],
                "recommended_next_action": "Review duplicate records and determine which to keep or merge",
                "validation_status": "pending"
            })
        return findings

    def _check_type_problems(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Check for data type problems."""
        findings = []
        for column in df.columns:
            # Check if column contains mixed types
            non_null_series = df[column].dropna()
            if len(non_null_series) > 0:
                # Get unique types in the column
                types = non_null_series.apply(type).unique()
                if len(types) > 1:
                    # Mixed types found
                    type_names = [t.__name__ for t in types]
                    example_rows = non_null_series.head(5).index.tolist()

                    findings.append({
                        "finding_id": f"mixed_types_{column}_{hash(str(types))}",
                        "issue_type": "type_problems",
                        "severity": "medium",
                        "affected_columns": [column],
                        "affected_count": len(non_null_series),
                        "affected_percent": round((len(non_null_series) / len(df)) * 100, 2),
                        "evidence": {
                            "description": f"Column '{column}' contains mixed data types: {', '.join(type_names)}",
                            "example_row_indices": example_rows,
                            "example_values": non_null_series.loc[example_rows].tolist(),
                            "detected_types": type_names
                        },
                        "possible_causes": ["Data import issues", "Manual data entry errors", "System interface problems"],
                        "recommended_next_action": "Standardize column to a single data type",
                        "validation_status": "pending"
                    })
        return findings

    def _check_date_issues(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Check for invalid dates and mixed date formats."""
        findings = []
        date_columns = df.select_dtypes(include=['datetime64']).columns.tolist()

        # Also check object columns that might contain dates
        object_columns = df.select_dtypes(include=['object']).columns
        for column in object_columns:
            # Try to parse as datetime
            try:
                parsed = pd.to_datetime(df[column], errors='coerce')
                null_count = parsed.isnull().sum()
                total_count = len(df)
                if null_count > 0 and null_count < total_count * 0.5:  # Some but not all failed
                    # Check if we have multiple date formats
                    # This is a simplified check - in reality we'd analyze the format patterns
                    non_null_original = df[column].dropna()
                    if len(non_null_original) > 0:
                        sample_values = non_null_original.head(10).tolist()
                        findings.append({
                            "finding_id": f"invalid_dates_{column}_{hash(str(sample_values))}",
                            "issue_type": "invalid_dates",
                            "severity": "medium",
                            "affected_columns": [column],
                            "affected_count": int(null_count),
                            "affected_percent": round((null_count / total_count) * 100, 2),
                            "evidence": {
                                "description": f"Column '{column}' contains {null_count} invalid or unparseable date values",
                                "example_row_indices": df[df[column].isnull() | parsed.isnull()].index[:5].tolist(),
                                "example_values": df.loc[df[df[column].isnull() | parsed.isnull()].index[:5], column].tolist(),
                                "sample_original_values": sample_values
                            },
                            "possible_causes": ["Mixed date formats", "Data entry errors", "System locale differences"],
                            "recommended_next_action": "Standardize date format and correct invalid entries",
                            "validation_status": "pending"
                        })
            except Exception:
                # If parsing fails completely, skip
                pass

        return findings

    def _check_category_issues(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Check for category spelling, case and whitespace variants."""
        findings = []
        object_columns = df.select_dtypes(include=['object']).columns

        for column in object_columns:
            non_null_series = df[column].dropna()
            if len(non_null_series) > 0:
                # Convert to string and strip whitespace
                str_series = non_null_series.astype(str).str.strip()
                # Check for case variants
                lower_series = str_series.str.lower()

                # Group by lowercase version to find case/whitespace variants
                grouped = str_series.groupby(lower_series).groups

                variant_groups = {k: v for k, v in grouped.items() if len(v) > 1}

                for lower_value, indices in variant_groups.items():
                    # Get the original values for this group
                    original_values = str_series.loc[indices].unique()
                    if len(original_values) > 1:  # Actually has variants
                        example_indices = list(indices)[:5]

                        findings.append({
                            "finding_id": f"category_variants_{column}_{hash(str(original_values))}",
                            "issue_type": "category_variants",
                            "severity": "low",
                            "affected_columns": [column],
                            "affected_count": len(indices),
                            "affected_percent": round((len(indices) / len(df)) * 100, 2),
                            "evidence": {
                                "description": f"Column '{column}' has {len(original_values)} spelling/case/whitespace variants for value '{lower_value}'",
                                "variant_values": original_values.tolist(),
                                "example_row_indices": example_indices,
                                "example_values": str_series.loc[example_indices].tolist()
                            },
                            "possible_cases": ["Inconsistent data entry", "Different data sources", "Manual correction errors"],
                            "recommended_next_action": "Standardize category values using consistent casing and trimming",
                            "validation_status": "pending"
                        })
        return findings

    def _check_out_of_range_numbers(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Check for out-of-range numbers based on business rules."""
        findings = []
        numeric_columns = df.select_dtypes(include=[np.number]).columns

        for column in numeric_columns:
            # Check configured ranges
            if column in self.business_rules["value_ranges"]:
                min_val, max_val = self.business_rules["value_ranges"][column]
                out_of_range = df[(df[column] < min_val) | (df[column] > max_val) & df[column].notnull()]
                out_of_range_count = len(out_of_range)

                if out_of_range_count > 0:
                    example_rows = out_of_range.index[:5].tolist()

                    findings.append({
                        "finding_id": f"out_of_range_{column}_{hash(str((min_val, max_val)))}",
                        "issue_type": "out_of_range_numbers",
                        "severity": "medium",
                        "affected_columns": [column],
                        "affected_count": out_of_range_count,
                        "affected_percent": round((out_of_range_count / len(df)) * 100, 2),
                        "evidence": {
                            "description": f"Column '{column}' has {out_of_range_count} values outside valid range [{min_val}, {max_val}]",
                            "example_row_indices": example_rows,
                            "example_values": out_of_range[column].tolist()[:5],
                            "valid_range": [min_val, max_val]
                        },
                        "possible_causes": ["Data entry errors", "System malfunctions", "Unit conversion errors"],
                        "recommended_next_action": "Investigate out-of-range values and correct or investigate root cause",
                        "validation_status": "pending"
                    })

            # Also check for negative values in fields that shouldn't be negative
            if column in self.business_rules["non_negative"]:
                negative_count = (df[column] < 0).sum()
                if negative_count > 0:
                    example_rows = df[df[column] < 0].index[:5].tolist()

                    findings.append({
                        "finding_id": f"negative_values_{column}_{hash(str(negative_count))}",
                        "issue_type": "negative_values",
                        "severity": "medium",
                        "affected_columns": [column],
                        "affected_count": int(negative_count),
                        "affected_percent": round((negative_count / len(df)) * 100, 2),
                        "evidence": {
                            "description": f"Column '{column}' has {negative_count} negative values",
                            "example_row_indices": example_rows,
                            "example_values": df.loc[example_rows, column].tolist()
                        },
                        "possible_causes": ["Data entry errors", "Calculation errors", "System bugs"],
                        "recommended_next_action": "Review negative values and determine if they are valid or errors",
                        "validation_status": "pending"
                    })
        return findings

    def _check_business_rules(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Check for business rule violations."""
        findings = []

        # Date order checks
        for date_pair in self.business_rules["date_order"]:
            start_col, end_col = date_pair
            if start_col in df.columns and end_col in df.columns:
                # Check if end date is before start date
                try:
                    start_dates = pd.to_datetime(df[start_col], errors='coerce')
                    end_dates = pd.to_datetime(df[end_col], errors='coerce')

                    # Only check rows where both dates are valid
                    valid_both = start_dates.notnull() & end_dates.notnull()
                    if valid_both.any():
                        invalid_order = (end_dates < start_dates) & valid_both
                        invalid_count = invalid_order.sum()

                        if invalid_count > 0:
                            example_rows = df[invalid_order].index[:5].tolist()

                            findings.append({
                                "finding_id": f"date_order_{start_col}_{end_col}_{hash(str(invalid_count))}",
                                "issue_type": "business_rule_violation",
                                "severity": "high",
                                "affected_columns": [start_col, end_col],
                                "affected_count": int(invalid_count),
                                "affected_percent": round((invalid_count / len(df)) * 100, 2),
                                "evidence": {
                                    "description": f"In {invalid_count} rows, '{end_col}' is before '{start_col}'",
                                    "example_row_indices": example_rows,
                                    "example_start_dates": start_dates.loc[example_rows].dt.strftime('%Y-%m-%d').tolist(),
                                    "example_end_dates": end_dates.loc[example_rows].dt.strftime('%Y-%m-%d').tolist()
                                },
                                "possible_causes": ["Data entry errors", "System logic errors", "Incorrect data migration"],
                                "recommended_next_action": "Review date pairs and correct order where necessary",
                                "validation_status": "pending"
                            })
                except Exception:
                    # If date parsing fails, skip this check
                    pass

        return findings

    def _check_contradictory_fields(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Check for contradictory field combinations."""
        findings = []

        # Example: gender and pregnancy check (simplified)
        # In a real system, these would be configurable
        contradictory_rules = [
            # (condition_columns, condition_values, contradiction_columns, contradiction_values, description)
        ]

        # For now, we'll implement a simple example
        # Check for people over 65 working full-time (example rule)
        if 'age' in df.columns and 'employment_status' in df.columns:
            try:
                over_65_fulltime = (df['age'] > 65) & (df['employment_status'].astype(str).str.contains('full.*time', case=False, na=False))
                count = over_65_fulltime.sum()

                if count > 0:
                    example_rows = df[over_65_fulltime].index[:5].tolist()

                    findings.append({
                        "finding_id": f"contradictory_age_employment_{hash(str(count))}",
                        "issue_type": "contradictory_fields",
                        "severity": "low",
                        "affected_columns": ['age', 'employment_status'],
                        "affected_count": int(count),
                        "affected_percent": round((count / len(df)) * 100, 2),
                        "evidence": {
                            "description": f"Found {count} people over 65 marked as full-time employed",
                            "example_row_indices": example_rows,
                            "example_ages": df.loc[example_rows, 'age'].tolist(),
                            "example_employment": df.loc[example_rows, 'employment_status'].tolist()
                        },
                        "possible_causes": ["Data entry errors", "Outdated records", "System integration issues"],
                        "recommended_next_action": "Review these records for accuracy",
                        "validation_status": "pending"
                    })
            except Exception:
                # Skip if there are issues with the check
                pass

        return findings

    def _get_severity_from_percent(self, percent: float) -> str:
        """Determine severity based on percentage of affected data."""
        if percent >= 30:
            return "critical"
        elif percent >= 15:
            return "high"
        elif percent >= 5:
            return "medium"
        else:
            return "low"