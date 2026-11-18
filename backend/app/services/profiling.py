import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import json
import math

class ProfilingService:
    def __init__(self):
        pass

    def _convert_to_native_types(self, obj):
        """
        Recursively convert numpy types to native Python types for JSON serialization.
        """
        if isinstance(obj, dict):
            return {key: self._convert_to_native_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_to_native_types(item) for item in obj]
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif pd.isna(obj):
            return None
        else:
            return obj

    def profile_dataset(self, file_path: str, format_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Profile a dataset and return a dictionary of profiling results.
        """
        from app.services.tabular_format import read_tabular
        df = read_tabular(file_path, format_metadata)

        # Basic dataset info
        profile = {
            "dataset_info": {
                "num_rows": len(df),
                "num_columns": len(df.columns),
                "memory_usage": int(df.memory_usage(deep=True).sum()),  # Convert to int
                "columns": list(df.columns)
            },
            "column_profiles": {}
        }

        # Profile each column
        for column in df.columns:
            col_profile = self._profile_column(df[column])
            profile["column_profiles"][column] = col_profile

        # Convert numpy types to native Python types
        profile = self._convert_to_native_types(profile)
        return profile

    def _profile_column(self, series: pd.Series) -> Dict[str, Any]:
        """
        Profile a single column.
        """
        profile = {
            "name": series.name,
            "dtype": str(series.dtype),
            "missing_count": int(series.isnull().sum()),  # Convert to int
            "missing_percent": float((series.isnull().sum() / len(series)) * 100),
            "unique_count": int(series.nunique()),  # Convert to int
            "unique_percent": float((series.nunique() / len(series)) * 100) if len(series) > 0 else 0.0,
        }

        # If the column is numeric, compute additional statistics
        if pd.api.types.is_numeric_dtype(series):
            # Drop missing values for numeric calculations
            numeric_series = series.dropna()
            if len(numeric_series) > 0:
                profile.update({
                    "min": float(numeric_series.min()),
                    "max": float(numeric_series.max()),
                    "mean": float(numeric_series.mean()),
                    "median": float(numeric_series.median()),
                    "std": float(numeric_series.std()),
                    "variance": float(numeric_series.var()),
                    "quartiles": {
                        "25%": float(numeric_series.quantile(0.25)),
                        "50%": float(numeric_series.quantile(0.50)),
                        "75%": float(numeric_series.quantile(0.75))
                    }
                })
            else:
                profile.update({
                    "min": None,
                    "max": None,
                    "mean": None,
                    "median": None,
                    "std": None,
                    "variance": None,
                    "quartiles": {
                        "25%": None,
                        "50%": None,
                        "75%": None
                    }
                })
        # If the column is datetime, compute datetime-specific stats
        elif pd.api.types.is_datetime64_any_dtype(series):
            # Convert to datetime if not already
            datetime_series = pd.to_datetime(series, errors='coerce')
            valid_dates = datetime_series.dropna()
            if len(valid_dates) > 0:
                profile.update({
                    "min_date": valid_dates.min().isoformat(),
                    "max_date": valid_dates.max().isoformat(),
                    "date_range_days": int((valid_dates.max() - valid_dates.min()).days),
                    "missing_dates": int(series.isnull().sum() + (series.notnull() & datetime_series.isnull()).sum())
                })
            else:
                profile.update({
                    "min_date": None,
                    "max_date": None,
                    "date_range_days": None,
                    "missing_dates": int(series.isnull().sum())
                })
        # For categorical or object columns
        else:
            # Treat as categorical
            freq_counts = series.value_counts(dropna=False)
            top_values = freq_counts.head(10)
            profile.update({
                "value_counts": {
                    str(k): int(v) for k, v in top_values.items()
                } if not top_values.empty else {},
                "top_value": str(top_values.index[0]) if len(top_values) > 0 else None,
                "top_value_freq": int(top_values.iloc[0]) if len(top_values) > 0 else 0,
                "entropy": float(self._calculate_entropy(series))
            })

        # Convert numpy types to native Python types
        profile = self._convert_to_native_types(profile)
        return profile

    def _calculate_entropy(self, series: pd.Series) -> float:
        """
        Calculate the entropy of a series (categorical).
        """
        # Drop missing values for entropy calculation
        clean_series = series.dropna()
        if len(clean_series) == 0:
            return 0.0
        value_counts = clean_series.value_counts()
        probabilities = value_counts / len(clean_series)
        entropy = -sum(p * math.log(p, 2) for p in probabilities if p > 0)
        return float(entropy)

    def get_profile_summary(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get a summary of the profiling results.
        """
        summary = {
            "total_rows": profile["dataset_info"]["num_rows"],
            "total_columns": profile["dataset_info"]["num_columns"],
            "total_missing_cells": sum(
                col["missing_count"] for col in profile["column_profiles"].values()
            ),
            "total_missing_percent": (
                sum(col["missing_count"] for col in profile["column_profiles"].values()) /
                (profile["dataset_info"]["num_rows"] * profile["dataset_info"]["num_columns"])
            ) * 100 if profile["dataset_info"]["num_rows"] > 0 and profile["dataset_info"]["num_columns"] > 0 else 0,
            "column_types": {}
        }

        # Count column types
        for col_name, col_profile in profile["column_profiles"].items():
            dtype = col_profile["dtype"]
            summary["column_types"][dtype] = summary["column_types"].get(dtype, 0) + 1

        # Convert numpy types to native Python types
        summary = self._convert_to_native_types(summary)
        return summary