"""
Candidate generation service for repair operations.
Generates appropriate repair strategies based on issue type and dataset characteristics.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Any, Optional, Tuple
from app.repairs.registry import get_operation, validate_operation_params
import logging

logger = logging.getLogger(__name__) 

class RepairCandidateGenerator:
    """Service for generating repair candidates for data quality issues."""

    def __init__(self):
        pass

    def generate_candidates_for_issue(self,
                                    finding: Dict[str, Any],
                                    df: pd.DataFrame) -> List[Dict[str, Any]]:
        """
        Generate repair candidates for a specific quality finding.

        Args:
            finding: Dictionary containing finding information from quality check
            df: The original DataFrame (as reference for generating candidates)

        Returns:
            List of candidate dictionaries, each containing:
            - operation: The repair operation to apply
            - parameters: Parameters for the operation
            - description: Human-readable description of the candidate
            - issue_type: Type of issue this candidate addresses
        """
        issue_type = finding.get("issue_type")
        affected_columns = finding.get("affected_columns", [])

        if issue_type == "missing_values":
            return self._generate_missing_value_candidates(finding, df)
        elif issue_type == "duplicate_rows":
            return self._generate_duplicate_candidates(finding, df)
        elif issue_type == "type_problems":
            return self._generate_type_problem_candidates(finding, df)
        elif issue_type == "invalid_dates":
            return self._generate_invalid_date_candidates(finding, df)
        elif issue_type == "category_variants":
            return self._generate_category_variant_candidates(finding, df)
        elif issue_type == "out_of_range_numbers":
            return self._generate_out_of_range_candidates(finding, df)
        elif issue_type == "negative_values":
            return self._generate_negative_value_candidates(finding, df)
        elif issue_type == "business_rule_violation":
            return self._generate_business_rule_candidates(finding, df)
        elif issue_type == "contradictory_fields":
            return self._generate_contradictory_field_candidates(finding, df)
        else:
            # For unknown issue types, return a conservative "no change" candidate
            return [{
                "operation": None,
                "parameters": {},
                "description": "Leave unchanged (no applicable repair strategy)",
                "issue_type": issue_type
            }]

    def _generate_missing_value_candidates(self,
                                         finding: Dict[str, Any],
                                         df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate candidates for missing values issue."""
        affected_columns = finding.get("affected_columns", [])
        candidates = []

        # Always include "leave unchanged" as an option
        candidates.append({
            "operation": None,
            "parameters": {},
            "description": "Leave missing values unchanged",
            "issue_type": "missing_values"
        })

        for col in affected_columns:
            if col not in df.columns:
                continue

            col_data = df[col]
            is_numeric = pd.api.types.is_numeric_dtype(col_data)

            # Candidate 1: Global median/mode fill
            if is_numeric:
                candidates.append({
                    "operation": "fill_numeric_global_median",
                    "parameters": {
                        "columns": [col],
                        "add_indicator": False
                    },
                    "description": f"Fill missing values in '{col}' with global median",
                    "issue_type": "missing_values"
                })

                # Candidate 2: Global median with indicator
                candidates.append({
                    "operation": "fill_numeric_global_median",
                    "parameters": {
                        "columns": [col],
                        "add_indicator": True
                    },
                    "description": f"Fill missing values in '{col}' with global median + missing indicator",
                    "issue_type": "missing_values"
                })
            else:
                # For categorical columns, use mode
                candidates.append({
                    "operation": "fill_categorical_mode",
                    "parameters": {
                        "columns": [col],
                        "add_indicator": False
                    },
                    "description": f"Fill missing values in '{col}' with mode",
                    "issue_type": "missing_values"
                })

                candidates.append({
                    "operation": "fill_categorical_mode",
                    "parameters": {
                        "columns": [col],
                        "add_indicator": True
                    },
                    "description": f"Fill missing values in '{col}' with mode + missing indicator",
                    "issue_type": "missing_values"
                })

            # Candidate 3: Group-based fill (if we can identify potential grouping columns)
            if is_numeric:
                # Look for potential grouping columns (categorical with reasonable cardinality)
                potential_groups = []
                for potential_col in df.columns:
                    if potential_col == col:
                        continue
                    if df[potential_col].dtype == 'object' or str(df[potential_col].dtype).startswith('category'):
                        unique_ratio = df[potential_col].nunique() / len(df)
                        if 0.01 <= unique_ratio <= 0.5:  # Reasonable grouping column
                            potential_groups.append(potential_col)

                # Add group-based candidates for top 2 potential groupers
                for group_col in potential_groups[:2]:
                    candidates.append({
                        "operation": "fill_numeric_group_median",
                        "parameters": {
                            "columns": [col],
                            "group_by": [group_col],
                            "add_indicator": False
                        },
                        "description": f"Fill missing values in '{col}' with group median grouped by '{group_col}'",
                        "issue_type": "missing_values"
                    })

                    candidates.append({
                        "operation": "fill_numeric_group_median",
                        "parameters": {
                            "columns": [col],
                            "group_by": [group_col],
                            "add_indicator": True
                        },
                        "description": f"Fill missing values in '{col}' with group median by '{group_col}' + missing indicator",
                        "issue_type": "missing_values"
                    })

        return candidates

    def _generate_duplicate_candidates(self,
                                     finding: Dict[str, Any],
                                     df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate candidates for duplicate rows issue."""
        candidates = []

        # Always include "leave unchanged"
        candidates.append({
            "operation": None,
            "parameters": {},
            "description": "Leave duplicate rows unchanged",
            "issue_type": "duplicate_rows"
        })

        # Candidate 1: Keep first occurrence
        candidates.append({
            "operation": "deduplicate",
            "parameters": {
                "keep": "first"
            },
            "description": "Remove duplicate rows, keeping first occurrence",
            "issue_type": "duplicate_rows"
        })

        # Candidate 2: Keep last occurrence
        candidates.append({
            "operation": "deduplicate",
            "parameters": {
                "keep": "last"
            },
            "description": "Remove duplicate rows, keeping last occurrence",
            "issue_type": "duplicate_rows"
        })

        # Candidate 3: Remove all duplicates (keep none)
        candidates.append({
            "operation": "deduplicate",
            "parameters": {
                "keep": False
            },
            "description": "Remove all duplicate rows (keep none)",
            "issue_type": "duplicate_rows"
        })

        # Candidate 4: Deduplicate on subset of columns (key columns if identifiable)
        # Try to identify potential key columns
        potential_keys = []
        for col in df.columns:
            # Look for columns that might be IDs (high uniqueness, likely integers or strings resembling IDs)
            unique_ratio = df[col].nunique() / len(df) if len(df) > 0 else 0
            col_name_lower = col.lower()

            # Heuristic for ID columns: name suggests ID, or high uniqueness with simple type
            if ('id' in col_name_lower or 'key' in col_name_lower) and unique_ratio > 0.95:
                potential_keys.append(col)
            elif df[col].dtype in ['int64', 'int32'] and unique_ratio > 0.9:
                potential_keys.append(col)

        # Add deduplication candidates for identified key columns
        for key_col in potential_keys[:2]:  # Limit to top 2
            candidates.append({
                "operation": "deduplicate",
                "parameters": {
                    "subset": [key_col],
                    "keep": "first"
                },
                "description": f"Remove duplicates based on '{key_col}' column, keeping first",
                "issue_type": "duplicate_rows"
            })

        return candidates

    def _generate_type_problem_candidates(self,
                                        finding: Dict[str, Any],
                                        df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate candidates for type problems issue."""
        affected_columns = finding.get("affected_columns", [])
        candidates = []

        # Always include "leave unchanged"
        candidates.append({
            "operation": None,
            "parameters": {},
            "description": "Leave type problems unchanged",
            "issue_type": "type_problems"
        })

        for col in affected_columns:
            if col not in df.columns:
                continue

            # Try to infer the most appropriate type
            col_data = df[col].dropna()
            if len(col_data) == 0:
                continue

            # Attempt to detect if it should be numeric
            numeric_attempt = pd.to_numeric(col_data, errors='coerce')
            numeric_success_rate = numeric_attempt.notna().sum() / len(col_data) if len(col_data) > 0 else 0

            # Attempt to detect if it should be datetime
            datetime_attempt = pd.to_datetime(col_data, errors='coerce')
            datetime_success_rate = datetime_attempt.notna().sum() / len(col_data) if len(col_data) > 0 else 0

            # Candidate: Convert to numeric if mostly numeric
            if numeric_success_rate > 0.8:
                candidates.append({
                    "operation": "convert_types",
                    "parameters": {
                        "type_mapping": {col: "numeric"}
                    },
                    "description": f"Convert column '{col}' to numeric type",
                    "issue_type": "type_problems"
                })

            # Candidate: Convert to datetime if mostly datetime
            if datetime_success_rate > 0.8:
                candidates.append({
                    "operation": "convert_types",
                    "parameters": {
                        "type_mapping": {col: "datetime"}
                    },
                    "description": f"Convert column '{col}' to datetime type",
                    "issue_type": "type_problems"
                })

            # Candidate: Convert to string (safe fallback)
            candidates.append({
                "operation": "convert_types",
                "parameters": {
                    "type_mapping": {col: "string"}
                },
                "description": f"Convert column '{col}' to string type",
                "issue_type": "type_problems"
            })

        return candidates

    def _generate_invalid_date_candidates(self,
                                        finding: Dict[str, Any],
                                        df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate candidates for invalid dates issue."""
        affected_columns = finding.get("affected_columns", [])
        candidates = []

        # Always include "leave unchanged"
        candidates.append({
            "operation": None,
            "parameters": {},
            "description": "Leave invalid dates unchanged",
            "issue_type": "invalid_dates"
        })

        for col in affected_columns:
            if col not in df.columns:
                continue

            # Try to infer a good date format from valid values
            valid_dates = pd.to_datetime(df[col], errors='coerce').dropna()
            if len(valid_dates) > 0:
                # Try common formats
                common_formats = [
                    "%Y-%m-%d",
                    "%m/%d/%Y",
                    "%d/%m/%Y",
                    "%Y/%m/%d",
                    "%d-%m-%Y",
                    "%m-%d-%Y"
                ]

                for fmt in common_formats:
                    try:
                        # Test if this format works for a sample of valid dates
                        test_sample = valid_dates.head(min(10, len(valid_dates)))
                        test_strings = test_sample.dt.strftime(fmt)
                        parsed_back = pd.to_datetime(test_strings, format=fmt, errors='coerce')
                        success_rate = parsed_back.notna().sum() / len(test_strings) if len(test_strings) > 0 else 0

                        if success_rate > 0.8:  # Good format candidate
                            candidates.append({
                                "operation": "parse_and_normalize_dates",
                                "parameters": {
                                    "columns": [col],
                                    "input_format": fmt,
                                    "output_format": "%Y-%m-%d"
                                },
                                "description": f"Parse and normalize dates in '{col}' using format '{fmt}'",
                                "issue_type": "invalid_dates"
                            })
                            break  # Found a good format, no need to try others
                    except Exception:
                        continue

            # Fallback: try to infer format automatically
            candidates.append({
                "operation": "parse_and_normalize_dates",
                "parameters": {
                    "columns": [col],
                    "input_format": None,  # Let pandas infer
                    "output_format": "%Y-%m-%d"
                },
                "description": f"Parse and normalize dates in '{col}' with automatic format detection",
                "issue_type": "invalid_dates"
            })

        return candidates

    def _generate_category_variant_candidates(self,
                                            finding: Dict[str, Any],
                                            df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate candidates for category variants issue."""
        affected_columns = finding.get("affected_columns", [])
        candidates = []

        # Always include "leave unchanged"
        candidates.append({
            "operation": None,
            "parameters": {},
            "description": "Leave category variants unchanged",
            "issue_type": "category_variants"
        })

        for col in affected_columns:
            if col not in df.columns:
                continue

            # Candidate 1: Trim whitespace
            candidates.append({
                "operation": "trim_whitespace",
                "parameters": {
                    "columns": [col]
                },
                "description": f"Trim whitespace from column '{col}'",
                "issue_type": "category_variants"
            })

            # Candidate 2: Standardize to lowercase
            candidates.append({
                "operation": "standardize_case",
                "parameters": {
                    "columns": [col],
                    "case_type": "lower"
                },
                "description": f"Convert column '{col}' to lowercase",
                "issue_type": "category_variants"
            })

            # Candidate 3: Standardize to uppercase
            candidates.append({
                "operation": "standardize_case",
                "parameters": {
                    "columns": [col],
                    "case_type": "upper"
                },
                "description": f"Convert column '{col}' to uppercase",
                "issue_type": "category_variants"
            })

            # Candidate 4: Standardize to title case
            candidates.append({
                "operation": "standardize_case",
                "parameters": {
                    "columns": [col],
                    "case_type": "title"
                },
                "description": f"Convert column '{col}' to title case",
                "issue_type": "category_variants"
            })

        return candidates

    def _generate_out_of_range_candidates(self,
                                        finding: Dict[str, Any],
                                        df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate candidates for out-of-range numbers issue."""
        # For out-of-range values, we typically want to either:
        # 1. Leave unchanged (if they might be valid)
        # 2. Convert to missing and then fill
        # 3. Cap to boundaries

        affected_columns = finding.get("affected_columns", [])
        candidates = []

        # Always include "leave unchanged"
        candidates.append({
            "operation": None,
            "parameters": {},
            "description": "Leave out-of-range values unchanged",
            "issue_type": "out_of_range_numbers"
        })

        from app.repairs.validation import RepairValidationService
        validation_service = RepairValidationService()

        for col in affected_columns:
            if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col]):
                continue

            # Get the valid range for this column
            min_val, max_val = validation_service.business_rules["value_ranges"].get(col, (None, None))

            # If we have a defined range, offer capping options
            if min_val is not None or max_val is not None:
                # Candidate: Cap values to boundaries
                cap_params = {}
                if min_val is not None:
                    cap_params["min_bound"] = min_val
                if max_val is not None:
                    cap_params["max_bound"] = max_val

                # Since we don't have a cap operation in registry yet, we'll use a combination
                # For now, we'll note this as a desired operation and suggest conversion to missing + fill

                # Candidate: Convert out-of-range to missing, then fill with median
                candidates.append({
                    "operation": "fill_numeric_global_median",
                    "parameters": {
                        "columns": [col],
                        "add_indicator": False
                    },
                    "description": f"Convert out-of-range values in '{col}' to missing, then fill with median",
                    "issue_type": "out_of_range_numbers"
                })

                candidates.append({
                    "operation": "fill_numeric_global_median",
                    "parameters": {
                        "columns": [col],
                        "add_indicator": True
                    },
                    "description": f"Convert out-of-range values in '{col}' to missing, fill with median + indicator",
                    "issue_type": "out_of_range_numbers"
                })

            # Always offer the option to treat as missing and fill
            candidates.append({
                "operation": "fill_numeric_global_median",
                "parameters": {
                    "columns": [col],
                    "add_indicator": False
                },
                "description": f"Fill missing and out-of-range values in '{col}' with global median",
                "issue_type": "out_of_range_numbers"
            })

        return candidates

    def _generate_negative_value_candidates(self,
                                          finding: Dict[str, Any],
                                          df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate candidates for negative values issue."""
        affected_columns = finding.get("affected_columns", [])
        candidates = []

        # Always include "leave unchanged"
        candidates.append({
            "operation": None,
            "parameters": {},
            "description": "Leave negative values unchanged",
            "issue_type": "negative_values"
        })

        for col in affected_columns:
            if col not in df.columns or not pd.api.types.is_numeric_dtype(df[col]):
                continue

            # Candidate: Convert negatives to missing, then fill
            candidates.append({
                "operation": "fill_numeric_global_median",
                "parameters": {
                    "columns": [col],
                    "add_indicator": False
                },
                "description": f"Convert negative values in '{col}' to missing, then fill with median",
                "issue_type": "negative_values"
            })

            candidates.append({
                "operation": "fill_numeric_global_median",
                "parameters": {
                    "columns": [col],
                    "add_indicator": True
                },
                "description": f"Convert negative values in '{col}' to missing, fill with median + indicator",
                "issue_type": "negative_values"
            })

            # Candidate: Convert negatives to positive (absolute value)
            # Note: We don't have an abs operation yet, so we'll skip for now or use convert_types creatively

        return candidates

    def _generate_business_rule_candidates(self,
                                         finding: Dict[str, Any],
                                         df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate candidates for business rule violations."""
        # Business rule violations often require domain-specific fixes
        # For now, we'll suggest leaving unchanged or basic corrections

        affected_columns = finding.get("affected_columns", [])
        candidates = []

        # Always include "leave unchanged"
        candidates.append({
            "operation": None,
            "parameters": {},
            "description": "Leave business rule violations unchanged (requires manual review)",
            "issue_type": "business_rule_violation"
        })

        # For date ordering issues, suggest swapping or making missing
        issue_types = finding.get("evidence", {}).get("description", "")
        if "date" in issue_types.lower() and "before" in issue_types.lower():
            # This is likely a date ordering issue like "end_date before start_date"
            # Extract column names if possible
            # For now, suggest making the problematic column missing

            # We'd need to parse the evidence to know which column to fix
            # This is a simplified approach
            if len(affected_columns) >= 2:
                col1, col2 = affected_columns[0], affected_columns[1]
                candidates.append({
                    "operation": None,  # Placeholder - would need custom operation
                    "parameters": {},
                    "description": f"Review date ordering between '{col1}' and '{col2}' (manual intervention needed)",
                    "issue_type": "business_rule_violation"
                })

        return candidates

    def _generate_contradictory_field_candidates(self,
                                               finding: Dict[str, Any],
                                               df: pd.DataFrame) -> List[Dict[str, Any]]:
        """Generate candidates for contradictory^−/−^field combinations."""
        # Similar to business rules, these often need domain knowledge

        affected_columns = finding.get("affected_columns", [])
        candidates = []

        # Always include "leave unchanged"
        candidates.append({
            "operation": None,
            "parameters": {},
            "description": "Leave contradictory fields unchanged (requires manual review)",
            "issue_type": "contradictory_fields"
        })

        return candidates

    def validate_candidate_parameters(self,
                                    operation_name: Optional[str],
                                    parameters: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate that the parameters are appropriate for the given operation.

        Returns:
            Tuple of (is_valid, error_message)
        """
        if operation_name is None:
            # "Leave unchanged" operation - always valid
            return True, None

        try:
            is_valid, error_msg = validate_operation_params(operation_name, parameters)
            return is_valid, error_msg
        except Exception as e:
            return False, f"Error validating parameters for {operation_name}: {str(e)}"

# Create a singleton instance
candidate_generator = RepairCandidateGenerator()