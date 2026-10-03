"""
Comprehensive TreeSHAP Model Working, Mechanisms, and Architecture PDF Generator.
Generates an executive, publication-grade PDF in the user's Downloads folder.
"""

import os
import sys
import shutil
import tempfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# ReportLab imports
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

# Pipeline & Model imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.config import PipelineConfig
from src.generator import MoSPIDataGenerator
from src.feature_pipeline import TemporalFeatureExtractor
from src.ml_engine import DualRiskEngine
from src.risk_calibration import RiskCalibrator
from src.tree_shap_engine import TreeSHAPEngine


class NumberedCanvas(canvas.Canvas):
    """Adds professional header and 'Page X of Y' footer on every page."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_decorations(num_pages)
            super().showPage()
        super().save()

    def draw_page_decorations(self, page_count):
        self.saveState()
        self.setFont("Helvetica-Bold", 8)
        self.setFillColor(colors.HexColor("#6c757d"))
        
        # Header (pages > 1)
        if self._pageNumber > 1:
            self.drawString(54, 755, "MoSPI Dhrishti Early Warning Platform — TreeSHAP Explainability Architecture")
            self.setStrokeColor(colors.HexColor("#dee2e6"))
            self.setLineWidth(0.5)
            self.line(54, 748, 558, 748)

        # Footer
        self.setFont("Helvetica", 8)
        self.drawString(54, 36, "CONFIDENTIAL & PROPRIETARY — MINISTRY OF STATISTICS & PROGRAMME IMPLEMENTATION")
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(558, 36, page_text)
        self.setStrokeColor(colors.HexColor("#dee2e6"))
        self.setLineWidth(0.5)
        self.line(54, 48, 558, 48)
        self.restoreState()


def generate_architecture_diagram(save_path: str):
    """Generates an architectural flow block diagram using matplotlib."""
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=300)
    ax.axis("off")

    # Define boxes
    boxes = [
        {"x": 0.05, "y": 0.55, "w": 0.22, "h": 0.35, "title": "1. Telemetry Ingestion", "desc": "• Monthly physical progress %\n• Cumulative capex & burn\n• Milestones planned vs achieved\n• Text remarks signals", "color": "#e8f4f8", "border": "#1d3557"},
        {"x": 0.38, "y": 0.55, "w": 0.24, "h": 0.35, "title": "2. Dual Tree Ensembles", "desc": "• XGBoost Cost Classifier\n• XGBoost Delay Classifier\n• Platt Probability Calibration\n• Composite 0-100 Scoring", "color": "#f1faee", "border": "#2a9d8f"},
        {"x": 0.73, "y": 0.55, "w": 0.23, "h": 0.35, "title": "3. TreeSHAP Engine", "desc": "• Polynomial O(TLD^2) exact\n• Dual-Objective combination\n• Top 3 risk accelerators (+)\n• Top 2 mitigating dampers (-)", "color": "#fefae0", "border": "#e76f51"},
        {"x": 0.22, "y": 0.08, "w": 0.26, "h": 0.32, "title": "4. Alert & Risk Routing", "desc": "• Critical threshold (>=75)\n• Trajectory escalation filter\n• Secretary review dispatch", "color": "#faedcd", "border": "#d4a373"},
        {"x": 0.58, "y": 0.08, "w": 0.28, "h": 0.32, "title": "5. Portal Dashboard API", "desc": "• Waterfall breakdowns\n• What-If intervention simulation\n• Review recommendation", "color": "#f8f9fa", "border": "#457b9d"},
    ]

    for b in boxes:
        rect = plt.Rectangle((b["x"], b["y"]), b["w"], b["h"], facecolor=b["color"], edgecolor=b["border"], linewidth=1.5, transform=ax.transAxes, zorder=2)
        ax.add_patch(rect)
        ax.text(b["x"] + 0.015, b["y"] + b["h"] - 0.06, b["title"], fontsize=9.5, fontweight="bold", color=b["border"], transform=ax.transAxes, zorder=3)
        ax.text(b["x"] + 0.015, b["y"] + 0.03, b["desc"], fontsize=7.5, color="#2b2d42", transform=ax.transAxes, zorder=3, va="bottom")

    # Add connecting arrows
    arrow_props = dict(arrowstyle="->", color="#343a40", lw=1.8, mutation_scale=12)
    ax.annotate("", xy=(0.38, 0.72), xytext=(0.27, 0.72), xycoords="axes fraction", arrowprops=arrow_props)
    ax.annotate("", xy=(0.73, 0.72), xytext=(0.62, 0.72), xycoords="axes fraction", arrowprops=arrow_props)
    ax.annotate("", xy=(0.35, 0.40), xytext=(0.50, 0.55), xycoords="axes fraction", arrowprops=arrow_props)
    ax.annotate("", xy=(0.72, 0.40), xytext=(0.84, 0.55), xycoords="axes fraction", arrowprops=arrow_props)
    ax.annotate("", xy=(0.58, 0.24), xytext=(0.48, 0.24), xycoords="axes fraction", arrowprops=arrow_props)

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight", dpi=300)
    plt.close(fig)


def generate_risk_trajectory_chart(df_risk: pd.DataFrame, project_id: str, save_path: str):
    """Generates monthly risk score progression with alert boundaries."""
    p_data = df_risk[df_risk["project_id"] == project_id].sort_values("snapshot_month")
    
    fig, ax = plt.subplots(figsize=(10, 4.2), dpi=300)
    months = p_data["snapshot_month"].values
    scores = p_data["composite_risk_score"].values

    ax.plot(months, scores, marker="o", color="#e63946", linewidth=2.5, label="Composite Risk Score (0-100)")
    ax.axhspan(75, 100, color="#d90429", alpha=0.15, label="Critical Tier (>=75)")
    ax.axhspan(50, 75, color="#f77f00", alpha=0.12, label="High Tier (50-75)")
    ax.axhspan(25, 50, color="#fcbf49", alpha=0.10, label="Medium Tier (25-50)")
    ax.axhspan(0, 25, color="#2a9d8f", alpha=0.10, label="Low Tier (<25)")

    ax.set_xlabel("Snapshot Month", fontsize=10, fontweight="bold")
    ax.set_ylabel("Risk Score", fontsize=10, fontweight="bold")
    ax.set_title(f"Early Warning Trajectory: Project {project_id}", fontsize=12, fontweight="bold")
    ax.set_ylim(0, 105)
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.legend(loc="upper left", fontsize=8.5, framealpha=0.9)

    for m, s in zip(months, scores):
        ax.text(m, s + 2.5, f"{s:.1f}", ha="center", fontsize=8, fontweight="bold")

    plt.tight_layout()
    plt.savefig(save_path, bbox_inches="tight", dpi=300)
    plt.close(fig)


def build_treeshap_pdf(output_pdf_path: str):
    """Builds the comprehensive PDF report with diagrams, mathematics, and live SHAP charts."""
    print(f"Training models and generating TreeSHAP figures for PDF...")
    
    # 1. Train pipeline models on sample dataset
    config = PipelineConfig(n_projects=30, min_snapshots=8, max_snapshots=16, random_seed=42)
    generator = MoSPIDataGenerator(config)
    df_raw = generator.generate_dataset()

    extractor = TemporalFeatureExtractor(config)
    extractor.fit(df_raw)
    X_features = extractor.transform(df_raw)

    ml_engine = DualRiskEngine(config)
    ml_engine.train_and_evaluate(X_features, df_raw, n_splits=3)

    calibrator = RiskCalibrator(config)
    calibrator.fit_calibrators(
        ml_engine.cost_cls_xgb,
        ml_engine.delay_cls_xgb,
        X_features,
        df_raw[config.features.TARGET_COST_CLASS].values,
        df_raw[config.features.TARGET_DELAY_CLASS].values
    )
    df_risk = calibrator.annotate_dataframe_with_risk(
        df_raw, X_features, ml_engine.cost_cls_xgb, ml_engine.delay_cls_xgb
    )

    tree_engine = TreeSHAPEngine(
        cost_model=ml_engine.cost_cls_xgb,
        delay_model=ml_engine.delay_cls_xgb,
        feature_names=list(X_features.columns)
    )

    # 2. Pick a high risk project for demo visualization
    high_risk_projects = df_risk[df_risk["risk_tier"] == "Critical"]["project_id"].unique()
    sample_pid = high_risk_projects[0] if len(high_risk_projects) > 0 else df_risk["project_id"].iloc[0]
    sample_mask = (df_risk["project_id"] == sample_pid)
    latest_month = df_risk[sample_mask]["snapshot_month"].max()
    sample_row_idx = df_risk[(df_risk["project_id"] == sample_pid) & (df_risk["snapshot_month"] == latest_month)].index[0]
    sample_instance = X_features.iloc[[sample_row_idx]]

    # 3. Create temp charts
    temp_dir = tempfile.mkdtemp()
    waterfall_img_path = os.path.join(temp_dir, "shap_waterfall.png")
    summary_img_path = os.path.join(temp_dir, "shap_summary.png")
    arch_img_path = os.path.join(temp_dir, "arch_diagram.png")
    traj_img_path = os.path.join(temp_dir, "risk_traj.png")

    tree_engine.generate_waterfall_plot(sample_instance, project_id=sample_pid, save_path=waterfall_img_path)
    tree_engine.generate_summary_plot(X_features, save_path=summary_img_path)
    generate_architecture_diagram(arch_img_path)
    generate_risk_trajectory_chart(df_risk, sample_pid, traj_img_path)

    # 4. Setup ReportLab Styles
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        "DocTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        textColor=colors.HexColor("#1d3557"),
        spaceAfter=6
    )
    subtitle_style = ParagraphStyle(
        "DocSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#457b9d"),
        spaceAfter=14
    )
    h1_style = ParagraphStyle(
        "Heading1_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        leading=18,
        textColor=colors.HexColor("#1d3557"),
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )
    h2_style = ParagraphStyle(
        "Heading2_Custom",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#2a9d8f"),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    body_style = ParagraphStyle(
        "Body_Custom",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor("#2b2d42"),
        spaceAfter=6
    )
    math_style = ParagraphStyle(
        "Math_Custom",
        parent=styles["Normal"],
        fontName="Courier-Bold",
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#1d3557"),
        backColor=colors.HexColor("#f1faee"),
        borderPadding=6,
        spaceAfter=8
    )

    doc = SimpleDocTemplate(
        output_pdf_path,
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    story = []

    # Title & Metadata
    story.append(Paragraph("TreeSHAP Model Working & Explainability Architecture", title_style))
    story.append(Paragraph("Technical Specification & Decision-Support Framework for MoSPI Dhrishti Platform", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#1d3557"), spaceAfter=12))

    # Executive Summary
    story.append(Paragraph("1. Executive Summary & Problem Context", h1_style))
    story.append(Paragraph(
        "The Ministry of Statistics and Programme Implementation (MoSPI) monitors central infrastructure projects "
        "costing over ₹150 Crore. To prevent catastrophic cost overruns and multi-year deadline misses, an automated "
        "<b>Early Warning & Decision-Support System</b> integrates machine learning with game-theoretic model explainability. "
        "Using <b>TreeSHAP (Tree SHapley Additive exPlanations)</b>, the platform provides exact, local, and mathematically "
        "rigorous root-cause attributions for every project risk alert, giving project officers transparent drivers rather than black-box scores.",
        body_style
    ))

    # Architecture Overview & Flow Diagram
    story.append(Spacer(1, 4))
    story.append(Paragraph("2. End-to-End System & Explainability Architecture", h1_style))
    story.append(Paragraph(
        "The architecture operates across five synchronized pipeline stages from ingestion to executive dashboard dispatch:",
        body_style
    ))
    story.append(Image(arch_img_path, width=7.0 * inch, height=3.15 * inch))
    story.append(Spacer(1, 8))

    # Mathematical Foundations
    story.append(Paragraph("3. Mathematical Foundations of TreeSHAP", h1_style))
    story.append(Paragraph(
        "TreeSHAP calculates the contribution of each feature $i$ to the predicted risk $f(x)$ relative to the expected model outcome $E[f(x)]$. "
        "Rooted in cooperative game theory, it satisfies the four essential axioms of explainability: <b>Efficiency</b>, <b>Symmetry</b>, <b>Dummy</b>, and <b>Additivity</b>.",
        body_style
    ))
    story.append(Paragraph(
        "<b>Efficiency (Additivity Axiom):</b><br/>"
        "f(x) = E[f(x)] + &Sigma; &phi;<sub>i</sub>(x)",
        math_style
    ))
    story.append(Paragraph(
        "<b>Polynomial Computational Efficiency:</b><br/>"
        "While model-agnostic KernelSHAP requires exponential O(2<sup>|F|</sup>) evaluations, TreeSHAP leverages decision tree topology "
        "to compute exact Shapley values in polynomial time <b>O(T &middot; L &middot; D<sup>2</sup>)</b>, where T is the number of trees, "
        "L is the maximum number of leaves, and D is the maximum tree depth.",
        body_style
    ))

    # Multi-Objective Combination
    story.append(Paragraph("4. Multi-Objective Dual Risk Attribution", h2_style))
    story.append(Paragraph(
        "Because project risk encompasses both financial overruns and temporal delays, the TreeSHAP Engine calculates dual Shapley vectors "
        "across both calibrated XGBoost classifiers and combines them into an actionable composite impact vector:",
        body_style
    ))
    story.append(Paragraph(
        "&phi;<sub>i</sub><sup>composite</sup> = w<sub>cost</sub> &middot; &phi;<sub>i</sub><sup>cost</sup> + w<sub>delay</sub> &middot; &phi;<sub>i</sub><sup>delay</sup><br/>"
        "where w<sub>cost</sub> = 0.5 and w<sub>delay</sub> = 0.5.",
        math_style
    ))

    story.append(PageBreak())

    # Visual SHAP Charts & Explanations
    story.append(Paragraph("5. Visual Explanations: Global & Local Risk Attributions", h1_style))
    story.append(Paragraph(
        "<b>Figure 1: Global Feature Importance (Top System Drivers across All Projects)</b><br/>"
        "Aggregates the mean absolute Shapley values E[|&phi;<sub>i</sub>|] showing which telemetry metrics most strongly dictate project health.",
        body_style
    ))
    story.append(Image(summary_img_path, width=6.8 * inch, height=3.4 * inch))
    story.append(Spacer(1, 8))

    story.append(Paragraph(
        f"<b>Figure 2: Local Project Waterfall Attribution (Project: {sample_pid})</b><br/>"
        "Deconstructs the exact margin push from baseline expectation to final predicted risk score, isolating positive risk accelerators from mitigating dampers.",
        body_style
    ))
    story.append(Image(waterfall_img_path, width=6.8 * inch, height=3.4 * inch))

    story.append(PageBreak())

    # Alert Mechanics & Dashboard Delivery
    story.append(Paragraph("6. Early Warning Trigger Mechanics & Trajectory Tracking", h1_style))
    story.append(Paragraph(
        "Warnings on the portal dashboard are not static thresholds. They evaluate continuous monthly trajectories "
        "derived from calibrated probabilities:",
        body_style
    ))
    story.append(Image(traj_img_path, width=6.8 * inch, height=2.85 * inch))
    story.append(Spacer(1, 6))

    # Table of Alert Triggers
    story.append(Paragraph("<b>Table 1: Alert Trigger Conditions & Decision Matrix</b>", h2_style))
    table_data = [
        ["Risk Tier", "Score Range", "Trend Condition", "Portal Alert Action", "Escalation Level"],
        ["Critical", ">= 75.0", "Any", "Immediate Active Alert Card", "Cabinet / Secretary Review"],
        ["High", "50.0 - 74.9", "Increasing (+2.0 pts)", "Priority Early Warning Alert", "Targeted Intervention Queue"],
        ["Medium", "25.0 - 49.9", "Stable / Decreasing", "Standard Monitoring Status", "Implementing Agency Lead"],
        ["Low", "< 25.0", "Any", "Green Status / On Track", "Routine Dashboard Logging"]
    ]
    t = Table(table_data, colWidths=[1.1*inch, 1.1*inch, 1.4*inch, 1.8*inch, 1.6*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1d3557")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#ced4da")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fa")]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(t)
    story.append(Spacer(1, 10))

    # Dashboard & API Integration
    story.append(Paragraph("7. Dashboard & Portal API Integration Points", h1_style))
    story.append(Paragraph(
        "The TreeSHAP Engine produces JSON-serializable payloads designed for seamless integration with custom frontend portals:",
        body_style
    ))
    story.append(Paragraph(
        "• <b>GET /projects/{project_id}/explanation</b>: Delivers top 3 risk drivers, top 2 mitigating factors, and waterfall steps for live rendering.<br/>"
        "• <b>GET /alerts</b>: Queries all projects triggering Critical or High-Escalating warning criteria.<br/>"
        "• <b>POST /projects/{project_id}/simulate</b>: Evaluates hypothetical officer interventions (e.g. land clearance resolution) in real-time.",
        body_style
    ))

    # Build Document
    try:
        doc.build(story, canvasmaker=NumberedCanvas)
        print(f"Successfully generated PDF at: {output_pdf_path}")
        return output_pdf_path
    finally:
        # Clean up temporary chart images
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    user_downloads = os.path.join(os.path.expanduser("~"), "Downloads")
    downloads_dir = user_downloads if os.path.exists(user_downloads) else os.getcwd()
    os.makedirs(downloads_dir, exist_ok=True)
    target_pdf = os.path.join(downloads_dir, "TreeSHAP_Model_Working_And_Architecture.pdf")
    build_treeshap_pdf(target_pdf)
