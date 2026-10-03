"""
Module 6: Officer-Capacity Optimization (MCDA / Decision Layer)
Uses OR-Tools linear solver (0-1 Knapsack MILP) with guaranteed fallback to optimize officer review queue under capacity constraints.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, List
from ortools.linear_solver import pywraplp
from .config import PipelineConfig

class OfficerCapacityOptimizer:
    """
    Optimizes the allocation of limited officer review time across high-risk projects
    to maximize overall portfolio risk reduction.
    """
    
    def __init__(self, config: PipelineConfig = None):
        self.config = config or PipelineConfig()

    def optimize_review_queue(
        self, 
        df_risk: pd.DataFrame, 
        officer_capacity_hours: float = 120.0
    ) -> Dict[str, Any]:
        """
        Solves 0-1 Integer Linear Program (Knapsack) for officer assignment:
        Maximize sum(x_i * Delta_R_i) s.t. sum(x_i * h_i) <= C, x_i in {0, 1}.
        """
        # Filter latest snapshot per project
        latest_df = df_risk.sort_values("snapshot_month").groupby("project_id").last().reset_index()
        high_risk_df = latest_df[latest_df["composite_risk_score"] >= self.config.thresholds.MEDIUM_MIN].copy()
        
        # Fallback if no projects meet Medium threshold: include top candidate projects
        if len(high_risk_df) < 3:
            high_risk_df = latest_df.sort_values("composite_risk_score", ascending=False).head(max(5, len(latest_df))).copy()
            
        if len(high_risk_df) == 0:
            return {
                "status": "No candidate projects available.",
                "officer_capacity_hours": officer_capacity_hours,
                "total_hours_allocated": 0.0,
                "capacity_utilization_pct": 0.0,
                "total_risk_mitigated": 0.0,
                "n_projects_selected": 0,
                "total_high_risk_candidates": 0,
                "selected_projects_queue": []
            }

        # Calculate estimated review hours required (h_i) and risk reduction impact (Delta R_i)
        high_risk_df["required_review_hours"] = (
            10.0 + (high_risk_df["unresolved_land_issues"] * 10.0) +
            (high_risk_df["unresolved_approval_issues"] * 8.0) +
            np.clip(high_risk_df["original_cost"] / 1000.0, 2.0, 15.0)
        ).round(1)
        
        high_risk_df["risk_reduction_impact"] = (
            (high_risk_df["composite_risk_score"] * 0.4) +
            (high_risk_df["unresolved_land_issues"] * 15.0) +
            (high_risk_df["unresolved_approval_issues"] * 12.0)
        ).round(1)
        
        # Initialize OR-Tools CBC / SCIP Mixed Integer Programming solver
        solver = pywraplp.Solver.CreateSolver("CBC")
        if not solver:
            solver = pywraplp.Solver.CreateSolver("SCIP")
            
        N = len(high_risk_df)
        selected_projects = []
        total_hours_used = 0.0
        total_risk_mitigated = 0.0
        solver_success = False
        
        if solver:
            x = {}
            for i in range(N):
                x[i] = solver.BoolVar(f"x_{i}")
                
            # Capacity Constraint: sum(x_i * h_i) <= C
            capacity_constraint = solver.Constraint(0, officer_capacity_hours, "CapacityConstraint")
            for i in range(N):
                capacity_constraint.SetCoefficient(x[i], float(high_risk_df.iloc[i]["required_review_hours"]))
                
            # Objective: Maximize sum(x_i * Delta_R_i)
            objective = solver.Objective()
            for i in range(N):
                objective.SetCoefficient(x[i], float(high_risk_df.iloc[i]["risk_reduction_impact"]))
            objective.SetMaximization()
            
            status = solver.Solve()
            
            if status in [pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE]:
                for i in range(N):
                    if x[i].solution_value() > 0.5:
                        row = high_risk_df.iloc[i]
                        selected_projects.append(self._format_project_row(row))
                        total_hours_used += float(row["required_review_hours"])
                        total_risk_mitigated += float(row["risk_reduction_impact"])
                if len(selected_projects) > 0:
                    solver_success = True
                    
        # Guaranteed Knapsack Fallback if OR-Tools solver produces no items
        if not solver_success:
            items = [self._format_project_row(high_risk_df.iloc[i]) for i in range(N)]
            # Sort by density (value / weight ratio)
            sorted_items = sorted(
                items, 
                key=lambda it: it["risk_reduction_impact"] / (it["required_review_hours"] + 1e-5), 
                reverse=True
            )
            for item in sorted_items:
                if total_hours_used + item["required_review_hours"] <= officer_capacity_hours:
                    selected_projects.append(item)
                    total_hours_used += item["required_review_hours"]
                    total_risk_mitigated += item["risk_reduction_impact"]

        # Sort selected review queue by risk reduction impact descending
        selected_projects = sorted(selected_projects, key=lambda p: p["risk_reduction_impact"], reverse=True)
        
        return {
            "status": "OPTIMAL" if solver_success else "GREEDY_KNAPSACK_FALLBACK",
            "officer_capacity_hours": officer_capacity_hours,
            "total_hours_allocated": round(total_hours_used, 1),
            "capacity_utilization_pct": round((total_hours_used / max(1e-5, officer_capacity_hours)) * 100.0, 1) if officer_capacity_hours > 0 else 0.0,
            "total_risk_mitigated": round(total_risk_mitigated, 1),
            "n_projects_selected": len(selected_projects),
            "total_high_risk_candidates": N,
            "selected_projects_queue": selected_projects
        }

    def _format_project_row(self, row: pd.Series) -> Dict[str, Any]:
        return {
            "project_id": str(row["project_id"]),
            "sector": str(row["sector"]),
            "ministry": str(row["ministry"]),
            "composite_risk_score": float(row["composite_risk_score"]),
            "risk_tier": str(row["risk_tier"]),
            "required_review_hours": float(row["required_review_hours"]),
            "risk_reduction_impact": float(row["risk_reduction_impact"]),
            "unresolved_land_issues": int(row["unresolved_land_issues"]),
            "unresolved_approval_issues": int(row["unresolved_approval_issues"]),
            "remarks_text": str(row["remarks_text"])
        }
