"""
Analytics Agent — handles charts, statistical analysis, and custom Python scripts.
Uses CrewAI with custom @tool-decorated functions for matplotlib, seaborn, and exec().
"""

import io
import os
import sys
import base64
import json
import traceback        
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns
from tenacity import retry, stop_after_attempt, wait_exponential
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

# ── Global reference to the active DataFrame ──
_active_df: pd.DataFrame = None
_generated_charts: list = []


def set_active_df(df: pd.DataFrame):
    global _active_df, _generated_charts
    _active_df = df.copy()
    _generated_charts = []


def get_generated_charts() -> list:
    return _generated_charts


def _fig_to_base64(fig) -> str:
    """Convert a matplotlib figure to base64 PNG string."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor="#1a1a2e", edgecolor="none")
    buf.seek(0)
    b64 = base64.b64encode(buf.read()).decode("utf-8")
    plt.close(fig)
    return b64


def _apply_dark_theme():
    """Apply a dark theme to matplotlib plots."""
    plt.style.use("dark_background")
    plt.rcParams.update({
        "figure.facecolor": "#1a1a2e",
        "axes.facecolor": "#16213e",
        "axes.edgecolor": "#8b5cf6",
        "axes.labelcolor": "#e2e8f0",
        "text.color": "#e2e8f0",
        "xtick.color": "#94a3b8",
        "ytick.color": "#94a3b8",
        "grid.color": "#334155",
        "grid.alpha": 0.3,
        "font.family": "sans-serif",
        "font.size": 11,
    })


# ═══════════════════════════════════════════
# TOOLS
# ═══════════════════════════════════════════

@tool("View Data Summary")
def view_data_summary(num_rows: int = 5) -> str:
    """View the first N rows and basic info about the dataset.
    Use this to understand the data before performing analysis.
    Args:
        num_rows: Number of rows to preview (default 5)
    """
    global _active_df
    if _active_df is None:
        return "No sheet loaded."
    
    info = f"Shape: {_active_df.shape[0]} rows × {_active_df.shape[1]} columns\n"
    info += f"Columns: {list(_active_df.columns)}\n"
    info += f"Data types:\n{_active_df.dtypes.to_string()}\n\n"
    info += f"First {num_rows} rows:\n{_active_df.head(num_rows).to_string()}\n\n"
    info += f"Missing values:\n{_active_df.isnull().sum().to_string()}"
    return info


@tool("Describe Statistics")
def describe_statistics(dummy: str = "") -> str:
    """Generate descriptive statistics for all numeric columns.
    Returns count, mean, std, min, 25%, 50%, 75%, max for each numeric column.
    """
    global _active_df
    if _active_df is None:
        return "No sheet loaded."
    try:
        desc = _active_df.describe(include="all").to_string()
        return f"Statistical Summary:\n{desc}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool("Create Chart")
def create_chart(chart_type: str, x_column: str, y_column: str = "", title: str = "Chart") -> str:
    """Create a chart/visualization from the data.
    Args:
        chart_type: Type of chart - one of: bar, line, scatter, pie, histogram, box, heatmap
        x_column: Column name for X-axis (or the main data column for pie/histogram)
        y_column: Column name for Y-axis (not needed for pie, histogram, or heatmap)
        title: Chart title
    """
    global _active_df, _generated_charts
    if _active_df is None:
        return "No sheet loaded."
    
    try:
        _apply_dark_theme()
        fig, ax = plt.subplots(figsize=(10, 6))
        
        chart_type = chart_type.lower().strip()
        
        if chart_type == "bar":
            if y_column:
                data = _active_df.groupby(x_column)[y_column].sum().sort_values(ascending=False).head(20)
            else:
                data = _active_df[x_column].value_counts().head(20)
            bars = ax.bar(range(len(data)), data.values, color=sns.color_palette("viridis", len(data)))
            ax.set_xticks(range(len(data)))
            ax.set_xticklabels(data.index, rotation=45, ha="right")
            ax.set_ylabel(y_column if y_column else "Count")
            
        elif chart_type == "line":
            if y_column:
                ax.plot(_active_df[x_column], _active_df[y_column], color="#8b5cf6", linewidth=2, marker="o", markersize=4)
                ax.set_ylabel(y_column)
            else:
                ax.plot(_active_df[x_column], color="#8b5cf6", linewidth=2)
            ax.set_xlabel(x_column)
            
        elif chart_type == "scatter":
            if not y_column:
                return "Scatter plot requires both x_column and y_column."
            scatter = ax.scatter(_active_df[x_column], _active_df[y_column],
                              c=range(len(_active_df)), cmap="viridis", alpha=0.7, s=50)
            ax.set_xlabel(x_column)
            ax.set_ylabel(y_column)
            plt.colorbar(scatter, ax=ax, label="Index")
            
        elif chart_type == "pie":
            data = _active_df[x_column].value_counts().head(10)
            if data.empty:
                return f"No data available in column '{x_column}' to plot."
            # Ensure valid data array for pie chart to prevent empty sequence error
            values = data.values.tolist()
            labels = data.index.tolist()
            
            # Use a categorical palette that matches our new Amber/Crimson theme
            colors = sns.color_palette("autumn", len(values))
            
            ax.pie(values, labels=labels, colors=colors, autopct="%1.1f%%",
                   textprops={"color": "#1e1b4b", "fontweight": "bold"})
        elif chart_type == "histogram":
            ax.hist(_active_df[x_column].dropna(), bins=30, color="#8b5cf6", alpha=0.8, edgecolor="#1a1a2e")
            ax.set_xlabel(x_column)
            ax.set_ylabel("Frequency")
            
        elif chart_type == "box":
            if y_column:
                _active_df.boxplot(column=y_column, by=x_column, ax=ax)
                plt.suptitle("")
            else:
                _active_df[[x_column]].boxplot(ax=ax)
            
        elif chart_type == "heatmap":
            numeric_df = _active_df.select_dtypes(include="number")
            if numeric_df.empty:
                return "No numeric columns found for heatmap."
            corr = numeric_df.corr()
            sns.heatmap(corr, annot=True, cmap="viridis", ax=ax, fmt=".2f",
                       linewidths=0.5, linecolor="#1a1a2e")
        else:
            return f"Unknown chart type: {chart_type}. Use: bar, line, scatter, pie, histogram, box, heatmap."
        
        ax.set_title(title, fontsize=14, fontweight="bold", color="#e2e8f0")
        fig.tight_layout()
        
        b64 = _fig_to_base64(fig)
        if b64 not in _generated_charts:
            _generated_charts.append(b64)
            return f"Chart '{title}' ({chart_type}) created successfully. Chart index: {len(_generated_charts) - 1}."
        else:
            return f"Chart '{title}' ({chart_type}) was already created. I do not need to create it again."
    except Exception as e:
        plt.close("all")
        return f"Error creating chart: {str(e)}"


@tool("Correlation Matrix")
def correlation_matrix(dummy: str = "") -> str:
    """Compute and visualize the correlation matrix for all numeric columns.
    Returns both the correlation values and generates a heatmap chart.
    """
    global _active_df, _generated_charts
    if _active_df is None:
        return "No sheet loaded."
    try:
        numeric_df = _active_df.select_dtypes(include="number")
        if numeric_df.empty:
            return "No numeric columns found."
        
        corr = numeric_df.corr()
        
        _apply_dark_theme()
        fig, ax = plt.subplots(figsize=(10, 8))
        sns.heatmap(corr, annot=True, cmap="viridis", ax=ax, fmt=".2f",
                   linewidths=0.5, linecolor="#1a1a2e", vmin=-1, vmax=1)
        ax.set_title("Correlation Matrix", fontsize=14, fontweight="bold", color="#e2e8f0")
        fig.tight_layout()
        
        b64 = _fig_to_base64(fig)
        _generated_charts.append(b64)
        
        return f"Correlation Matrix:\n{corr.to_string()}\n\nHeatmap generated. Chart index: {len(_generated_charts) - 1}."
    except Exception as e:
        plt.close("all")
        return f"Error: {str(e)}"


@tool("Value Counts")
def value_counts(column_name: str, top_n: int = 20) -> str:
    """Get the count of each unique value in a column.
    Args:
        column_name: Column to count values for
        top_n: Show top N values (default 20)
    """
    global _active_df
    if _active_df is None:
        return "No sheet loaded."
    try:
        if column_name not in _active_df.columns:
            return f"Column '{column_name}' not found. Available: {list(_active_df.columns)}"
        vc = _active_df[column_name].value_counts().head(top_n)
        return f"Value counts for '{column_name}':\n{vc.to_string()}\n\nTotal unique values: {_active_df[column_name].nunique()}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool("Group Analysis")
def group_analysis(group_column: str, agg_column: str, agg_function: str = "mean") -> str:
    """Perform a groupby aggregation on the data.
    Args:
        group_column: Column to group by
        agg_column: Column to aggregate
        agg_function: Aggregation function - one of: mean, sum, count, min, max, median, std
    """
    global _active_df
    if _active_df is None:
        return "No sheet loaded."
    try:
        if group_column not in _active_df.columns:
            return f"Column '{group_column}' not found. Available: {list(_active_df.columns)}"
        if agg_column not in _active_df.columns:
            return f"Column '{agg_column}' not found. Available: {list(_active_df.columns)}"
        
        result = _active_df.groupby(group_column)[agg_column].agg(agg_function)
        return f"Group analysis ({agg_function} of '{agg_column}' by '{group_column}'):\n{result.to_string()}"
    except Exception as e:
        return f"Error: {str(e)}"


@tool("Run Python Script")
def run_python_script(script: str) -> str:
    """Execute a Python script with access to the DataFrame for custom analysis.
    The DataFrame is available as the variable 'df'. You can use pandas, numpy, matplotlib, seaborn.
    Any print() output will be captured. For charts, use plt.savefig() or the script will auto-capture.
    
    Args:
        script: Python code to execute. The DataFrame is available as 'df'.
    """
    global _active_df, _generated_charts
    if _active_df is None:
        return "No sheet loaded."
    
    try:
        _apply_dark_theme()
        
        # Capture stdout
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        # Execute with df in scope
        local_vars = {
            "df": _active_df.copy(),
            "pd": pd,
            "np": __import__("numpy"),
            "plt": plt,
            "sns": sns,
        }
        
        exec(script, {"__builtins__": __builtins__}, local_vars)
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        # Check if any plots were created
        fig_nums = plt.get_fignums()
        if fig_nums:
            for num in fig_nums:
                fig = plt.figure(num)
                b64 = _fig_to_base64(fig)
                _generated_charts.append(b64)
            output += f"\n[Generated {len(fig_nums)} chart(s). Chart indices: {list(range(len(_generated_charts) - len(fig_nums), len(_generated_charts)))}]"
        
        return output if output.strip() else "Script executed successfully (no output)."
    except Exception as e:
        sys.stdout = old_stdout
        plt.close("all")
        return f"Script error:\n{traceback.format_exc()}"


@tool("Find Value")
def find_value(query: str) -> str:
    """Find specific values or answer questions about the data using pandas operations.
    Args:
        query: A description of what to find, e.g. 'maximum salary', 'row where name is John',
               'average of column Price', 'number of unique cities'
    """
    global _active_df
    if _active_df is None:
        return "No sheet loaded."
    try:
        result_parts = []
        q = query.lower()
        
        # Try to intelligently parse common queries
        for col in _active_df.columns:
            if col.lower() in q:
                if any(word in q for word in ["max", "maximum", "highest", "largest", "biggest"]):
                    if _active_df[col].dtype in ["int64", "float64"]:
                        max_val = _active_df[col].max()
                        max_row = _active_df[_active_df[col] == max_val].head(1)
                        result_parts.append(f"Maximum {col}: {max_val}\nRow:\n{max_row.to_string()}")
                elif any(word in q for word in ["min", "minimum", "lowest", "smallest"]):
                    if _active_df[col].dtype in ["int64", "float64"]:
                        min_val = _active_df[col].min()
                        min_row = _active_df[_active_df[col] == min_val].head(1)
                        result_parts.append(f"Minimum {col}: {min_val}\nRow:\n{min_row.to_string()}")
                elif any(word in q for word in ["average", "avg", "mean"]):
                    if _active_df[col].dtype in ["int64", "float64"]:
                        result_parts.append(f"Average {col}: {_active_df[col].mean():.4f}")
                elif any(word in q for word in ["sum", "total"]):
                    if _active_df[col].dtype in ["int64", "float64"]:
                        result_parts.append(f"Sum of {col}: {_active_df[col].sum()}")
                elif any(word in q for word in ["unique", "distinct"]):
                    result_parts.append(f"Unique values in {col}: {_active_df[col].nunique()}")
                elif any(word in q for word in ["count"]):
                    result_parts.append(f"Count of non-null {col}: {_active_df[col].count()}")
        
        if result_parts:
            return "\n\n".join(result_parts)
        
        # Fallback: provide general info
        summary = f"Dataset shape: {_active_df.shape}\nColumns: {list(_active_df.columns)}\n"
        summary += f"Numeric summary:\n{_active_df.describe().to_string()}"
        return summary
    except Exception as e:
        return f"Error: {str(e)}"


# ═══════════════════════════════════════════
# AGENT & CREW
# ═══════════════════════════════════════════

ALL_TOOLS = [
    view_data_summary, describe_statistics, create_chart,
    correlation_matrix, value_counts, group_analysis,
    run_python_script, find_value
]




@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=15, max=120),
    reraise=True
)
def run_analytics_agent(query: str, df: pd.DataFrame, model: str = "ollama/qwen2.5:7b") -> dict:
    """
    Run the Analytics agent on a user query with exponential backoff for rate limits.
    Returns: { "response": str, "charts": list[str(base64)] }
    """
    set_active_df(df)
    _generated_charts.clear()
    
    # Use OpenAI compatible endpoint for strict tool-calling
    local_llm = LLM(
        model=model.replace("ollama/", "openai/"),
        base_url="http://localhost:11434/v1",
        api_key="ollama"
    )

    agent = Agent(
        role="Data Analyst",
        goal="Provide clear, concise analytical insights and generate visual charts when requested.",
        backstory=(
            "You are a Senior Data Analyst. You use Python tools to create powerful visualizations "
            "and extract meaningful insights. Your answers are brief, accurate, and highly formatting."
        ),
        tools=ALL_TOOLS,
        verbose=False,
        max_iter=3,  # Restored for deeper reasoning and tool chaining
        allow_delegation=False,
        cache=False,
        llm=model,
    )

    task = Task(
        description=(
            f"The user wants to analyze their spreadsheet data:\n\n"
            f"\"{query}\"\n\n"
            f"First, use the appropriate tools (like describe_statistics, value_counts or view_data_summary) to calculate exact numbers and understand the data. "
            f"CRITICAL: If the user's prompt explicitly contains capitalized words that look like column names (e.g. 'Sales', 'Segment'), you MUST assume those are the exact column names and immediately call `create_chart` using them. Do not ask for clarification. "
            f"IMPORTANT: Call the `create_chart` tool EXACTLY ONCE. Do not generate multiple charts under any circumstances. "
            f"If the user asks for a chart or visualization, create it AFTER (or alongside) analyzing the data mathematically. "
            f"Finally, you MUST provide a beautifully formatted, highly concise Markdown response. Include headers, short bulleted lists, bolded key figures, and deep actionable insights. Do NOT write long paragraphs. Keep it brief. Do NOT use any emojis."
        ),
        expected_output="A professional, highly concise markdown response (max 3-4 bullet points, using bold text and headers) with deep analytical insights and precise numbers. Strictly NO emojis and NO long paragraphs.",
        agent=agent,
    )

    crew = Crew(
        agents=[agent],
        tasks=[task],
        process=Process.sequential,
        verbose=False,
    )

    result = crew.kickoff()
    result_str = str(result)
    
    # CrewAI often catches LLM exceptions and returns them as strings.
    # We must explicitly raise an exception so tenacity knows to sleep and retry.
    is_rate_limited = "RESOURCE_EXHAUSTED" in result_str or "429" in result_str or "exceeded your current quota" in result_str.lower()
    
    if is_rate_limited:
        raise Exception(f"Rate limited by LLM provider. Triggering Tenacity backoff sleep: {result_str}")

    charts = get_generated_charts()

    return {
        "response": result_str,
        "charts": charts,
    }
