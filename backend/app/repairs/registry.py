"""
Registry of allowed repair operations with validation.
Each operation is a function that takes a DataFrame and parameters,
returns a new DataFrame with the repair applied.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import re

class RepairOperationRegistry:
    """Registry of allowed repair operations."""

    @staticmethod
    def trim_whitespace(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """Trim whitespace from string columns."""
        df_copy = df.copy()
        columns = params.get("columns", df_copy.select_dtypes(include=['object']).columns)

        for col in columns:
            if col in df_copy.columns and df_copy[col].dtype == 'object':
                df_copy[col] = df_copy[col].astype(str).str.strip()
                # Convert "None"/"NaN" strings back to actual NaN
                df_copy[col] = df_copy[col].replace(['None', 'NaN', ''], np.nan)

        return df_copy

    @staticmethod
    def standardize_case(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """Standardize case for categorical columns (lower, upper, title)."""
        df_copy = df.copy()
        columns = params.get("columns", [])
        case_type = params.get("case_type", "lower")  # lower, upper, title

        if case_type not in ['lower', 'upper', 'title']:
            raise ValueError(f"Invalid case_type: {case_type}. Must be lower, upper, or title")

        for col in columns:
            if col in df_copy.columns and df_copy[col].dtype == 'object':
                if case_type == 'lower':
                    df_copy[col] = df_copy[col].str.lower()
                elif case_type == 'upper':
                    df_copy[col] = df_copy[col].str.upper()
                elif case_type == 'title':
                    df_copy[col] = df_copy[col].str.title()

                # Convert "none"/"nan" strings back to actual NaN
                df_copy[col] = df_copy[col].replace(['none', 'nan', ''], np.nan)

        return df_copy

    @staticmethod
    def explicit_category_mapping(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """Map category values according to explicit mapping."""
        df_copy = df.copy()
        column = params.get("column")
        mapping = params.get("mapping", {})  # {old_value: new_value}
        default_value = params.get("default_value", None)

        if not column or column not in df_copy.columns:
            raise ValueError(f"Column {column} not found in dataframe")

        if not mapping:
            return df_copy

        def map_value(val):
            if pd.isna(val):
                return val
            return mapping.get(val, default_value if default_value is not None else val)

        df_copy[column] = df_copy[column].apply(map_value)
        return df_copy

    @staticmethod
    def parse_and_normalize_dates(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """Parse and normalize date columns to a standard format."""
        df_copy = df.copy()
        columns = params.get("columns", [])
        input_format = params.get("input_format", None)  # If None, infer
        output_format = params.get("output_format", "%Y-%m-%d")

        for col in columns:
            if col not in df_copy.columns:
                continue

            try:
                if input_format:
                    parsed = pd.to_datetime(df_copy[col], format=input_format, errors='coerce')
                else:
                    parsed = pd.to_datetime(df_copy[col], errors='coerce')

                # Format as string in output format
                df_copy[col] = parsed.dt.strftime(output_format)
                # Convert NaT back to NaN for string representation
                df_copy[col] = df_copy[col].replace('NaT', np.nan)
            except Exception as e:
                # If parsing fails completely, leave column unchanged
                pass

        return df_copy

    @staticmethod
    def convert_types(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """Convert columns to specified data types."""
        df_copy = df.copy()
        type_mapping = params.get("type_mapping", {})  # {column: target_type}

        for col, target_type in type_mapping.items():
            if col not in df_copy.columns:
                continue

            try:
                if target_type == 'numeric':
                    df_copy[col] = pd.to_numeric(df_copy[col], errors='coerce')
                elif target_type == 'datetime':
                    df_copy[col] = pd.to_datetime(df_copy[col], errors='coerce')
                elif target_type == 'string':
                    df_copy[col] = df_copy[col].astype(str)
                    df_copy[col] = df_copy[col].replace('nan', np.nan)
                elif target_type == 'category':
                    df_copy[col] = df_copy[col].astype('category')
                else:
                    # Try direct conversion
                    df_copy[col] = df_copy[col].astype(target_type)
            except Exception:
                # If conversion fails, leave column unchanged
                pass

        return df_copy

    @staticmethod
    def fill_numeric_global_median(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """Fill missing numeric values with global median."""
        df_copy = df.copy()
        columns = params.get("columns", df_copy.select_dtypes(include=[np.number]).columns)
        add_indicator = params.get("add_indicator", False)

        for col in columns:
            if col not in df_copy.columns or not pd.api.types.is_numeric_dtype(df_copy[col]):
                continue

            if add_indicator:
                indicator_col = f"{col}_was_missing"
                df_copy[indicator_col] = df_copy[col].isna().astype(int)

            median_val = df_copy[col].median()
            df_copy[col] = df_copy[col].fillna(median_val)

        return df_copy

    @staticmethod
    def fill_numeric_group_median(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """Fill missing numeric values with group median."""
        df_copy = df.copy()
        columns = params.get("columns", [])
        group_by = params.get("group_by", [])
        add_indicator = params.get("add_indicator", False)

        if not columns:
            columns = df_copy.select_dtypes(include=[np.number]).columns

        if not group_by:
            # Fall back to global median if no group specified
            return RepairOperationRegistry.fill_numeric_global_median(df, params)

        # Validate group columns exist
        for col in group_by:
            if col not in df_copy.columns:
                raise ValueError(f"Group column {col} not found in dataframe")

        for col in columns:
            if col not in df_copy.columns or not pd.api.types.is_numeric_dtype(df_copy[col]):
                continue

            if add_indicator:
                indicator_col = f"{col}_was_missing"
                df_copy[indicator_col] = df_copy[col].isna().astype(int)

            # Compute group medians and fill
            group_medians = df_copy.groupby(group_by)[col].transform('median')
            df_copy[col] = df_copy[col].fillna(group_medians)

        return df_copy

    @staticmethod
    def fill_categorical_mode(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """Fill missing categorical values with mode."""
        df_copy = df.copy()
        columns = params.get("columns", df_copy.select_dtypes(include=['object', 'category']).columns)
        add_indicator = params.get("add_indicator", False)

        for col in columns:
            if col not in df_copy.columns:
                continue

            if add_indicator:
                indicator_col = f"{col}_was_missing"
                df_copy[indicator_col] = df_copy[col].isna().astype(int)

            mode_val = df_copy[col].mode()
            if not mode_val.empty:
                df_copy[col] = df_copy[col].fillna(mode_val.iloc[0])

        return df_copy

    @staticmethod
    def deduplicate(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """Remove duplicate rows based on specified policy."""
        df_copy = df.copy()
        subset = params.get("subset", None)  # Columns to consider for duplicates
        keep = params.get("keep", "first")   # first, last, False

        if keep not in ['first', 'last', False]:
            raise ValueError(f"Invalid keep parameter: {keep}. Must be first, last, or False")

        initial_count = len(df_copy)
        df_copy = df_copy.drop_duplicates(subset=subset, keep=keep)
        removed_count = initial_count - len(df_copy)

        # Store metadata about what was removed
        df_copy.attrs['deduplication_info'] = {
            'removed_count': removed_count,
            'removed_percent': (removed_count / initial_count * 100) if initial_count > 0 else 0,
            'subset': subset,
            'keep': keep
        }

        return df_copy

    @staticmethod
    def flag_outliers(df: pd.DataFrame, params: Dict[str, Any]) -> pd.DataFrame:
        """Flag outliers using IQR or z-score method (does not modify data, adds flag columns)."""
        df_copy = df.copy()
        columns = params.get("columns", df_copy.select_dtypes(include=[np.number]).columns)
        method = params.get("method", "iqr")  # iqr or zscore
        threshold = params.get("threshold", 1.5)  # For IQR: usually 1.5, for Z-score: usually 3

        for col in columns:
            if col not in df_copy.columns or not pd.api.types.is_numeric_dtype(df_copy[col]):
                continue

            # Skip if all values are NaN
            if df_copy[col].isna().all():
                continue

            if method == "iqr":
                Q1 = df_copy[col].quantile(0.25)
                Q3 = df_copy[col].quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - threshold * IQR
                upper_bound = Q3 + threshold * IQR
                outliers = (df_copy[col] < lower_bound) | (df_copy[col] > upper_bound)
            elif method == "zscore":
                from scipy import stats
                # Only compute z-score on non-NaN values
                non_nan_vals = df_copy[col].dropna()
                if len(non_nan_vals) > 0:
                    z_scores = np.abs(stats.zscore(non_nan_vals))
                    # Map back to original indices
                    outlier_mask = pd.Series(False, index=df_copy.index)
                    outlier_mask.loc[non_nan_vals.index] = z_scores > threshold
                    outliers = outlier_mask
                else:
                    outliers = pd.Series(False, index=df_copy.index)
            else:
                raise ValueError(f"Invalid method: {method}. Must be iqr or zscore")

            # Add flag column
            flag_col = f"{col}_is_outlier"
            df_copy[flag_col] = outliers.astype(int)

        return df_copy

# Create a singleton instance
repair_registry = RepairOperationRegistry()

# Mapping of operation names to functions for easy lookup
OPERATIONS = {
    "trim_whitespace": repair_registry.trim_whitespace,
    "standardize_case": repair_registry.standardize_case,
    "explicit_category_mapping": repair_registry.explicit_category_mapping,
    "parse_and_normalize_dates": repair_registry.parse_and_normalize_dates,
    "convert_types": repair_registry.convert_types,
    "fill_numeric_global_median": repair_registry.fill_numeric_global_median,
    "fill_numeric_group_median": repair_registry.fill_numeric_group_median,
    "fill_categorical_mode": repair_registry.fill_categorical_mode,
    "deduplicate": repair_registry.deduplicate,
    "flag_outliers": repair_registry.flag_outliers,
}

def get_operation(operation_name: str):
    """Get operation function by name."""
    if operation_name not in OPERATIONS:
        raise ValueError(f"Unknown operation: {operation_name}. Available: {list(OPERATIONS.keys())}")
    return OPERATIONS[operation_name]

def validate_operation_params(operation_name: str, params: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Validate parameters for a given operation."""
    try:
        # Basic validation - each operation will do more specific validation when applied
        if not isinstance(params, dict):
            return False, "Parameters must be a dictionary"

        # Operation-specific validation will happen in the operation functions
        return True, None
    except Exception as e:
        return False, str(e)