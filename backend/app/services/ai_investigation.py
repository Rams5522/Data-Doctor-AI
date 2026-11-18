"""
AI Investigation Service using LangGraph for agent orchestration.
Provides structured workflows for root cause analysis, pattern analysis, etc.
"""

import json
import logging
from typing import Dict, List, Any, Optional, TypedDict
from datetime import datetime
from enum import Enum

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from app.services.llm_service import llm_service, PromptTemplates
from app.services.knowledge_base import knowledge_base_service
from app.db.session import SessionLocal
from app.db.models import Dataset, DatasetVersion, QualityFinding


logger = logging.getLogger(__name__)


class InvestigationType(str, Enum):
    ROOT_CAUSE = "root_cause"
    PATTERN_ANALYSIS = "pattern_analysis"
    ANOMALY_DETECTION = "anomaly_detection"
    IMPACT_ASSESSMENT = "impact_assessment"
    REPAIR_RECOMMENDATION = "repair_recommendation"


class InvestigationState(TypedDict):
    """State for the investigation workflow."""
    dataset_id: int
    version_id: int
    investigation_type: str
    user_query: str
    dataset_context: Dict[str, Any]
    findings: List[Dict[str, Any]]
    findings_summary: str
    kb_context: List[Dict[str, Any]]
    repair_memory: List[Dict[str, Any]]
    analysis_result: Optional[str]
    recommendations: List[str]
    evidence: List[Dict[str, Any]]
    current_step: str
    error: Optional[str]


class AIInvestigationService:
    """Service for AI-powered data quality investigations using LangGraph."""

    def __init__(self):
        self.workflow = self._build_workflow()

    def _build_workflow(self) -> StateGraph:
        """Build the LangGraph workflow for investigations."""

        workflow = StateGraph(InvestigationState)

        # Define nodes
        workflow.add_node("gather_context", self._gather_context)
        workflow.add_node("search_knowledge_base", self._search_knowledge_base)
        workflow.add_node("search_repair_memory", self._search_repair_memory)
        workflow.add_node("generate_analysis", self._generate_analysis)
        workflow.add_node("generate_recommendations", self._generate_recommendations)
        workflow.add_node("compile_evidence", self._compile_evidence)

        # Define edges
        workflow.set_entry_point("gather_context")
        workflow.add_edge("gather_context", "search_knowledge_base")
        workflow.add_edge("search_knowledge_base", "search_repair_memory")
        workflow.add_edge("search_repair_memory", "generate_analysis")
        workflow.add_edge("generate_analysis", "generate_recommendations")
        workflow.add_edge("generate_recommendations", "compile_evidence")
        workflow.add_edge("compile_evidence", END)

        return workflow.compile(checkpointer=MemorySaver())

    def _gather_context(self, state: InvestigationState) -> InvestigationState:
        """Gather dataset and findings context."""
        try:
            db = SessionLocal()
            try:
                dataset = db.query(Dataset).filter(Dataset.id == state["dataset_id"]).first()
                version = db.query(DatasetVersion).filter(
                    DatasetVersion.id == state["version_id"],
                    DatasetVersion.dataset_id == state["dataset_id"]
                ).first()

                findings = db.query(QualityFinding).filter(
                    QualityFinding.dataset_id == state["dataset_id"],
                    QualityFinding.version_id == state["version_id"]
                ).all()

                # Get profiling info if available
                from app.db.models import DatasetProfile
                profile = db.query(DatasetProfile).filter(
                    DatasetProfile.dataset_id == state["dataset_id"],
                    DatasetProfile.version_id == state["version_id"]
                ).first()

                dataset_context = {
                    "dataset_id": state["dataset_id"],
                    "dataset_name": dataset.name if dataset else "Unknown",
                    "version_id": state["version_id"],
                    "version_number": version.version_number if version else 0,
                    "version_type": version.version_type if version else "unknown",
                    "num_rows": profile.profile_data.get("dataset_info", {}).get("num_rows", 0) if profile else 0,
                    "num_cols": profile.profile_data.get("dataset_info", {}).get("num_columns", 0) if profile else 0,
                }

                findings_list = []
                for f in findings:
                    findings_list.append({
                        "id": f.id,
                        "finding_id": f.finding_id,
                        "issue_type": f.issue_type,
                        "severity": f.severity,
                        "affected_columns": f.affected_columns or [],
                        "affected_count": f.affected_count,
                        "affected_percent": f.affected_percent,
                        "evidence": f.evidence or {},
                        "possible_causes": f.possible_causes or [],
                        "recommended_next_action": f.recommended_next_action or ""
                    })

                # Create findings summary for prompts
                findings_summary = self._summarize_findings(findings_list)

                state["dataset_context"] = dataset_context
                state["findings"] = findings_list
                state["findings_summary"] = findings_summary
                state["current_step"] = "context_gathered"

            finally:
                db.close()

        except Exception as e:
            state["error"] = f"Failed to gather context: {str(e)}"
            state["current_step"] = "error"

        return state

    def _summarize_findings(self, findings: List[Dict[str, Any]]) -> str:
        """Create a summary of findings for LLM prompts."""
        if not findings:
            return "No quality findings available."

        summary_parts = [f"Total findings: {len(findings)}"]

        # Group by issue type
        by_type = {}
        for f in findings:
            issue_type = f["issue_type"]
            if issue_type not in by_type:
                by_type[issue_type] = []
            by_type[issue_type].append(f)

        for issue_type, findings_list in by_type.items():
            total_affected = sum(f["affected_count"] for f in findings_list)
            max_severity = max(f["severity"] for f in findings_list)
            columns = set()
            for f in findings_list:
                columns.update(f["affected_columns"])
            summary_parts.append(
                f"- {issue_type}: {len(findings_list)} findings, "
                f"{total_affected} total affected, "
                f"max severity: {max_severity}, "
                f"columns: {', '.join(columns)}"
            )

        return "\n".join(summary_parts)

    def _search_knowledge_base(self, state: InvestigationState) -> InvestigationState:
        """Search knowledge base for relevant articles."""
        try:
            query = f"{state['user_query']} {state['findings_summary']}"
            articles = knowledge_base_service.search_articles(
                query=query,
                limit=5,
                min_similarity=0.25
            )
            state["kb_context"] = articles
            state["current_step"] = "kb_searched"
        except Exception as e:
            state["kb_context"] = []
            # Don't fail the whole workflow for KB search errors
            logger.warning(f"Knowledge base search failed: {e}")

        return state

    def _search_repair_memory(self, state: InvestigationState) -> InvestigationState:
        """Search repair memory for similar past repairs."""
        try:
            if state["findings"]:
                # Use the first finding's type for searching
                primary_finding = state["findings"][0]
                finding_type = primary_finding["issue_type"]

                repairs = knowledge_base_service.find_similar_repairs(
                    finding_type=finding_type,
                    dataset_context={
                        "num_rows": state["dataset_context"].get("num_rows", 0),
                        "num_cols": state["dataset_context"].get("num_cols", 0),
                        "version_type": state["dataset_context"].get("version_type", "original")
                    },
                    limit=3
                )
                state["repair_memory"] = repairs
            state["current_step"] = "repair_memory_searched"
        except Exception as e:
            state["repair_memory"] = []
            logger.warning(f"Repair memory search failed: {e}")

        return state

    def _generate_analysis(self, state: InvestigationState) -> InvestigationState:
        """Generate the main analysis using LLM."""
        try:
            # Select prompt template based on investigation type
            templates = {
                InvestigationType.ROOT_CAUSE: PromptTemplates.ROOT_CAUSE_ANALYSIS,
                InvestigationType.PATTERN_ANALYSIS: PromptTemplates.PATTERN_ANALYSIS,
                InvestigationType.ANOMALY_DETECTION: PromptTemplates.ANOMALY_DETECTION,
                InvestigationType.IMPACT_ASSESSMENT: PromptTemplates.IMPACT_ASSESSMENT,
                InvestigationType.REPAIR_RECOMMENDATION: PromptTemplates.REPAIR_RECOMMENDATION,
            }

            template = templates.get(
                InvestigationType(state["investigation_type"]),
                PromptTemplates.ROOT_CAUSE_ANALYSIS
            )

            # Prepare context for prompt
            kb_context_str = ""
            if state["kb_context"]:
                kb_context_str = "\n\nRelevant Knowledge Base Articles:\n"
                for article in state["kb_context"][:3]:
                    kb_context_str += f"- {article['title']} ({article['category']}): {article['content'][:300]}...\n"

            repair_memory_str = ""
            if state["repair_memory"]:
                repair_memory_str = "\n\nSimilar Past Repairs:\n"
                for repair in state["repair_memory"]:
                    repair_memory_str += f"- {repair['finding_type']}: {repair['operation']} with {repair['parameters']} (outcome: {repair['outcome']})\n"

            available_ops = [
                "trim_whitespace", "standardize_case", "explicit_category_mapping",
                "parse_and_normalize_dates", "convert_types", "fill_numeric_global_median",
                "fill_numeric_group_median", "fill_categorical_mode", "deduplicate", "flag_outliers"
            ]

            prompt = template.format(
                dataset_name=state["dataset_context"].get("dataset_name", "Unknown"),
                num_rows=state["dataset_context"].get("num_rows", 0),
                num_cols=state["dataset_context"].get("num_cols", 0),
                findings_summary=state["findings_summary"],
                user_query=state["user_query"],
                finding_details=json.dumps(state["findings"][0] if state["findings"] else {}, indent=2),
                available_operations=", ".join(available_ops),
                past_repairs=repair_memory_str
            ) + kb_context_str + repair_memory_str

            # Check if LLM is available
            if not llm_service.is_available():
                state["analysis_result"] = self._generate_fallback_analysis(state)
                state["current_step"] = "fallback_analysis_generated"
            else:
                system_prompt = "You are an expert data quality analyst. Provide clear, structured, evidence-based analysis."
                analysis = llm_service.generate(
                    prompt=prompt,
                    system_prompt=system_prompt,
                    temperature=0.3,
                    max_tokens=3000
                )
                state["analysis_result"] = analysis
                state["current_step"] = "analysis_generated"

        except Exception as e:
            state["analysis_result"] = f"Analysis generation failed: {str(e)}"
            state["current_step"] = "analysis_error"
            logger.error(f"Analysis generation failed: {e}")

        return state

    def _generate_fallback_analysis(self, state: InvestigationState) -> str:
        """Generate deterministic fallback analysis when LLM is unavailable."""
        findings = state["findings"]
        if not findings:
            return "No quality findings to analyze."

        analysis_parts = [
            f"**Deterministic Analysis (LLM Unavailable)**",
            f"Dataset: {state['dataset_context'].get('dataset_name', 'Unknown')} "
            f"({state['dataset_context'].get('num_rows', 0)} rows, "
            f"{state['dataset_context'].get('num_cols', 0)} columns)",
            f"Investigation Type: {state['investigation_type'].replace('_', ' ').title()}",
            f"User Query: {state['user_query']}",
            "",
            "**Findings Summary:**",
            state["findings_summary"],
            "",
            "**Automated Analysis:**"
        ]

        if state["investigation_type"] == InvestigationType.ROOT_CAUSE:
            analysis_parts.extend([
                "1. **Primary Root Causes:** Based on issue types detected:",
            ])
            for f in findings[:3]:
                analysis_parts.append(f"   - {f['issue_type'].replace('_', ' ').title()}: "
                                    f"Likely caused by data entry errors or system integration issues")

        elif state["investigation_type"] == InvestigationType.PATTERN_ANALYSIS:
            analysis_parts.extend([
                "1. **Recurring Patterns:**",
            ])
            issue_types = [f["issue_type"] for f in findings]
            from collections import Counter
            type_counts = Counter(issue_types)
            for issue_type, count in type_counts.most_common(3):
                analysis_parts.append(f"   - {issue_type}: {count} occurrences")

        elif state["investigation_type"] == InvestigationType.ANOMALY_DETECTION:
            analysis_parts.extend([
                "1. **Detected Anomalies:**",
            ])
            for f in findings[:5]:
                if f["severity"] in ["high", "critical"]:
                    analysis_parts.append(f"   - {f['issue_type']}: {f['affected_count']} affected "
                                        f"({f['affected_percent']:.1f}%) - {f['severity'].upper()} severity")

        elif state["investigation_type"] == InvestigationType.IMPACT_ASSESSMENT:
            critical_count = sum(1 for f in findings if f["severity"] == "critical")
            high_count = sum(1 for f in findings if f["severity"] == "high")
            analysis_parts.extend([
                "1. **Impact Assessment:**",
                f"   - Critical issues: {critical_count}",
                f"   - High severity issues: {high_count}",
                f"   - Total affected records: {sum(f['affected_count'] for f in findings)}",
                "   - Priority: Fix critical/high severity issues first"
            ])

        elif state["investigation_type"] == InvestigationType.REPAIR_RECOMMENDATION:
            analysis_parts.extend([
                "1. **Recommended Repairs:**",
            ])
            for f in findings[:3]:
                if f["issue_type"] == "missing_values":
                    analysis_parts.append(f"   - {f['issue_type']}: Try fill_numeric_global_median or fill_categorical_mode")
                elif f["issue_type"] == "duplicate_rows":
                    analysis_parts.append(f"   - {f['issue_type']}: Try deduplicate with keep='first'")
                elif f["issue_type"] == "category_variants":
                    analysis_parts.append(f"   - {f['issue_type']}: Try standardize_case + trim_whitespace")
                elif f["issue_type"] == "invalid_dates":
                    analysis_parts.append(f"   - {f['issue_type']}: Try parse_and_normalize_dates")
                else:
                    analysis_parts.append(f"   - {f['issue_type']}: Review recommended_next_action: {f['recommended_next_action']}")

        analysis_parts.extend([
            "",
            "**Note:** This is a deterministic fallback analysis. Configure an LLM provider (Ollama/OpenAI) "
            "in Settings for full AI-powered analysis with root cause reasoning and contextual recommendations."
        ])

        return "\n".join(analysis_parts)

    def _generate_recommendations(self, state: InvestigationState) -> InvestigationState:
        """Generate actionable recommendations."""
        try:
            if not llm_service.is_available() or not state.get("analysis_result"):
                # Generate basic recommendations from findings
                state["recommendations"] = self._generate_basic_recommendations(state)
            else:
                # Use LLM to generate recommendations based on analysis
                prompt = f"""Based on the following analysis, provide 5-7 specific, actionable recommendations:

Analysis:
{state['analysis_result']}

Dataset: {state['dataset_context'].get('dataset_name', 'Unknown')}
Findings: {state['findings_summary']}

Provide recommendations as a numbered list, each being specific and actionable."""

                recommendations_text = llm_service.generate(
                    prompt=prompt,
                    system_prompt="You are a data quality expert. Provide specific, actionable recommendations.",
                    temperature=0.3,
                    max_tokens=1500
                )

                # Parse recommendations from response
                state["recommendations"] = self._parse_recommendations(recommendations_text)

            state["current_step"] = "recommendations_generated"

        except Exception as e:
            state["recommendations"] = [f"Recommendation generation failed: {str(e)}"]
            logger.error(f"Recommendation generation failed: {e}")

        return state

    def _generate_basic_recommendations(self, state: InvestigationState) -> List[str]:
        """Generate basic recommendations from findings."""
        recommendations = []

        findings = state["findings"]
        if not findings:
            return ["No quality issues detected. No action needed."]

        # Map issue types to standard recommendations
        issue_recommendations = {
            "missing_values": "Use Repair Lab to generate and validate imputation strategies (global median, group median, mode)",
            "duplicate_rows": "Use Repair Lab to deduplicate (keep first/last/none based on business logic)",
            "type_problems": "Convert column to consistent type using convert_types operation",
            "invalid_dates": "Parse and normalize dates using parse_and_normalize_dates with detected format",
            "category_variants": "Standardize case and trim whitespace using standardize_case and trim_whitespace",
            "out_of_range_numbers": "Investigate outliers, consider capping or converting to missing then imputing",
            "negative_values": "Review if negative values are valid; if not, convert to missing and impute",
            "business_rule_violation": "Review business rules; may require manual correction or data source fix",
            "contradictory_fields": "Investigate contradictory records; likely requires domain expert review"
        }

        for finding in findings[:5]:
            issue_type = finding["issue_type"]
            if issue_type in issue_recommendations:
                rec = f"{issue_type.replace('_', ' ').title()}: {issue_recommendations[issue_type]}"
                recommendations.append(rec)

        if not recommendations:
            recommendations.append("Review quality findings in Quality Report and use Repair Lab for fixes")

        recommendations.extend([
            "Run profiling again after repairs to verify improvements",
            "Check Visualization Center for data distributions and correlations",
            "Document all repair decisions in audit trail"
        ])

        return recommendations[:7]

    def _parse_recommendations(self, text: str) -> List[str]:
        """Parse recommendations from LLM response."""
        recommendations = []
        for line in text.split("\n"):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith("-") or line.startswith("•")):
                # Remove numbering/bullets
                clean = line.lstrip("0123456789.-• ").strip()
                if clean:
                    recommendations.append(clean)
        return recommendations[:7] if recommendations else [text[:500]]

    def _compile_evidence(self, state: InvestigationState) -> InvestigationState:
        """Compile evidence and citations for the investigation."""
        evidence = []

        # Add findings as evidence
        for finding in state["findings"]:
            evidence.append({
                "type": "quality_finding",
                "source": "quality_check",
                "finding_id": finding["finding_id"],
                "issue_type": finding["issue_type"],
                "severity": finding["severity"],
                "description": finding["evidence"].get("description", ""),
                "affected_count": finding["affected_count"],
                "affected_percent": finding["affected_percent"],
                "columns": finding["affected_columns"]
            })

        # Add knowledge base articles as evidence
        for article in state["kb_context"][:3]:
            evidence.append({
                "type": "knowledge_base",
                "source": "knowledge_base",
                "article_id": article["id"],
                "title": article["title"],
                "category": article["category"],
                "similarity": article.get("similarity", 0),
                "excerpt": article["content"][:500]
            })

        # Add repair memory as evidence
        for repair in state["repair_memory"]:
            evidence.append({
                "type": "repair_memory",
                "source": "approved_repairs",
                "repair_id": repair["id"],
                "finding_type": repair["finding_type"],
                "operation": repair["operation"],
                "parameters": repair["parameters"],
                "outcome": repair["outcome"],
                "similarity": repair.get("similarity", 0)
            })

        state["evidence"] = evidence
        state["current_step"] = "completed"
        return state

    def run_investigation(self,
                          dataset_id: int,
                          version_id: int,
                          investigation_type: str,
                          user_query: str) -> Dict[str, Any]:
        """Run a complete investigation workflow."""
        initial_state: InvestigationState = {
            "dataset_id": dataset_id,
            "version_id": version_id,
            "investigation_type": investigation_type,
            "user_query": user_query,
            "dataset_context": {},
            "findings": [],
            "findings_summary": "",
            "kb_context": [],
            "repair_memory": [],
            "analysis_result": None,
            "recommendations": [],
            "evidence": [],
            "current_step": "started",
            "error": None
        }

        # Run the workflow
        config = {"configurable": {"thread_id": f"inv_{dataset_id}_{version_id}_{investigation_type}_{datetime.now().timestamp()}"}}
        final_state = self.workflow.invoke(initial_state, config=config)

        return {
            "dataset_id": dataset_id,
            "version_id": version_id,
            "investigation_type": investigation_type,
            "user_query": user_query,
            "analysis": final_state.get("analysis_result", ""),
            "recommendations": final_state.get("recommendations", []),
            "evidence": final_state.get("evidence", []),
            "knowledge_base_articles": final_state.get("kb_context", []),
            "similar_repairs": final_state.get("repair_memory", []),
            "dataset_context": final_state.get("dataset_context", {}),
            "status": "completed" if not final_state.get("error") else "error",
            "error": final_state.get("error"),
            "completed_at": datetime.now().isoformat()
        }


# Singleton instance
ai_investigation_service = AIInvestigationService()