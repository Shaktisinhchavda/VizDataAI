"""
Data Manager Agent — handles CRUD operations on spreadsheets.
Uses CrewAI with custom @tool-decorated functions for pandas operations.
"""

import json
import pandas as pd
from crewai import Agent, Task, Crew, Process, LLM
from crewai.tools import tool
from tenacity import retry, stop_after_attempt, wait_exponential

# ── Global reference to the active DataFrame ──
_active_df: pd.DataFrame = None
_df_modified: bool = False


def set_active_df(df: pd.DataFrame):
    global _active_df, _df_modified
    _active_df = df.copy()
    _df_modified = False


def get_active_df() -> pd.DataFrame:
    return _active_df


def was_modified() -> bool:
    return _df_modified


# ═══════════════════════════════════════════
# TOOLS
# ═══════════════════════════════════════════

@tool("View Sheet")
def view_sheet(num_rows: int = 10) -> str:
    """View the first N rows of the current spreadsheet along with column info.
    Use this tool to understand the data structure before making changes.
    Args:
        num_rows: Number of rows to display (default 10)
    """
    global _active_df
    if _active_df is None:
        return "No sheet loaded."
    
    info = f"Shape: {_active_df.shape[0]} rows × {_active_df.shape[1]} columns\n"
    info += f"Columns: {list(_active_df.columns)}\n"
    info += f"Data types:\n{_active_df.dtypes.to_string()}\n\n"
    info += f"First {num_rows} rows:\n{_active_df.head(num_rows).to_string()}"
    return info


@tool("Add Row")
def add_row(row_data: str) -> str:
    """Add a new row to the spreadsheet.
    Args:
        row_data: JSON string of column:value pairs (e.g. '{"Name": "John"}') or an array of values in order (e.g. '["John", 30]').
    """
    global _active_df, _df_modified
    if _active_df is None:
        return "No sheet loaded."
    try:
        data = json.loads(row_data)
        if isinstance(data, list):
            # Model passed a list of values instead of a dict mapping
            if len(data) > len(_active_df.columns):
                data = data[:len(_active_df.columns)]
            elif len(data) < len(_active_df.columns):
                data = data + [""] * (len(_active_df.columns) - len(data))
            new_row = pd.DataFrame([data], columns=_active_df.columns)
        elif isinstance(data, dict):
            new_row = pd.DataFrame([data])
        else:
            return "Invalid row_data format. Must be JSON dict or list."
            
        _active_df = pd.concat([_active_df, new_row], ignore_index=True)
        _df_modified = True
        return f"Row added successfully. New shape: {_active_df.shape[0]} rows × {_active_df.shape[1]} columns."
    except Exception as e:
        return f"Error adding row: {str(e)}"


@tool("Add Column")
def add_column(column_name: str, default_value: str = "") -> str:
    """Add a new column to the spreadsheet with a default value.
    Args:
        column_name: Name of the new column
        default_value: Default value for all rows (can be a number, text, or empty string)
    """
    global _active_df, _df_modified
    if _active_df is None:
        return "No sheet loaded."
    try:
        if column_name in _active_df.columns:
            return f"Column '{column_name}' already exists."
        _active_df[column_name] = default_value
        _df_modified = True
        return f"Column '{column_name}' added with default value '{default_value}'. Shape: {_active_df.shape[0]} rows × {_active_df.shape[1]} columns."
    except Exception as e:
        return f"Error adding column: {str(e)}"


@tool("Delete Row")
def delete_row(row_indices: str) -> str:
    """Delete one or more rows by their index numbers.
    Args:
        row_indices: Comma-separated row indices to delete, e.g. '0,1,5' or a single index '3'
    """
    global _active_df, _df_modified
    if _active_df is None:
        return "No sheet loaded."
    try:
        indices = [int(i.strip()) for i in row_indices.split(",")]
        invalid = [i for i in indices if i < 0 or i >= len(_active_df)]
        if invalid:
            return f"Invalid row indices: {invalid}. Valid range: 0 to {len(_active_df) - 1}."
        _active_df = _active_df.drop(indices).reset_index(drop=True)
        _df_modified = True
        return f"Deleted {len(indices)} row(s). New shape: {_active_df.shape[0]} rows × {_active_df.shape[1]} columns."
    except Exception as e:
        return f"Error deleting row: {str(e)}"


@tool("Delete Column")
def delete_column(column_names: str) -> str:
    """Delete one or more columns by name.
    Args:
        column_names: Comma-separated column names to delete, e.g. 'Age,Salary'
    """
    global _active_df, _df_modified
    if _active_df is None:
        return "No sheet loaded."
    try:
        cols = [c.strip() for c in column_names.split(",")]
        missing = [c for c in cols if c not in _active_df.columns]
        if missing:
            return f"Columns not found: {missing}. Available: {list(_active_df.columns)}"
        _active_df = _active_df.drop(columns=cols)
        _df_modified = True
        return f"Deleted column(s): {cols}. New shape: {_active_df.shape[0]} rows × {_active_df.shape[1]} columns."
    except Exception as e:
        return f"Error deleting column: {str(e)}"


@tool("Rename Column")
def rename_column(old_name: str, new_name: str) -> str:
    """Rename a column in the spreadsheet.
    Args:
        old_name: Current column name
        new_name: New column name
    """
    global _active_df, _df_modified
    if _active_df is None:
        return "No sheet loaded."
    try:
        if old_name not in _active_df.columns:
            return f"Column '{old_name}' not found. Available: {list(_active_df.columns)}"
        _active_df = _active_df.rename(columns={old_name: new_name})
        _df_modified = True
        return f"Column renamed from '{old_name}' to '{new_name}'."
    except Exception as e:
        return f"Error renaming column: {str(e)}"


@tool("Filter Data")
def filter_data(condition: str) -> str:
    """Filter rows based on a pandas query condition string.
    Args:
        condition: A pandas query string, e.g. 'Age > 30', 'City == "New York"', 'Salary > 50000 and Department == "Engineering"'
    """
    global _active_df, _df_modified
    if _active_df is None:
        return "No sheet loaded."
    try:
        filtered = _active_df.query(condition)
        _active_df = filtered.reset_index(drop=True)
        _df_modified = True
        return f"Filtered to {len(_active_df)} rows matching: {condition}."
    except Exception as e:
        return f"Error filtering: {str(e)}"


@tool("Sort Data")
def sort_data(column_name: str, ascending: bool = True) -> str:
    """Sort the spreadsheet by a column.
    Args:
        column_name: Column to sort by
        ascending: True for ascending (A-Z, 0-9), False for descending
    """
    global _active_df, _df_modified
    if _active_df is None:
        return "No sheet loaded."
    try:
        if column_name not in _active_df.columns:
            return f"Column '{column_name}' not found. Available: {list(_active_df.columns)}"
        _active_df = _active_df.sort_values(by=column_name, ascending=ascending).reset_index(drop=True)
        _df_modified = True
        return f"Sorted by '{column_name}' ({'ascending' if ascending else 'descending'}). Shape: {_active_df.shape[0]} rows."
    except Exception as e:
        return f"Error sorting: {str(e)}"


@tool("Fill Missing Values")
def fill_missing(column_name: str, fill_value: str = "0") -> str:
    """Fill missing (NaN) values in a specific column.
    Args:
        column_name: Column to fill missing values in
        fill_value: Value to fill with (will be auto-converted to the column's data type)
    """
    global _active_df, _df_modified
    if _active_df is None:
        return "No sheet loaded."
    try:
        if column_name not in _active_df.columns:
            return f"Column '{column_name}' not found. Available: {list(_active_df.columns)}"
        missing_count = _active_df[column_name].isna().sum()
        _active_df[column_name] = _active_df[column_name].fillna(fill_value)
        _df_modified = True
        return f"Filled {missing_count} missing values in '{column_name}' with '{fill_value}'."
    except Exception as e:
        return f"Error filling missing values: {str(e)}"


@tool("Update Cell")
def update_cell(row_index: int, column_name: str, new_value: str) -> str:
    """Update a specific cell in the spreadsheet.
    Args:
        row_index: Row index (0-based)
        column_name: Column name
        new_value: New value for the cell
    """
    global _active_df, _df_modified
    if _active_df is None:
        return "No sheet loaded."
    try:
        if column_name not in _active_df.columns:
            return f"Column '{column_name}' not found. Available: {list(_active_df.columns)}"
        if row_index < 0 or row_index >= len(_active_df):
            return f"Row index {row_index} out of range. Valid: 0 to {len(_active_df) - 1}."
        old_value = _active_df.at[row_index, column_name]
        _active_df.at[row_index, column_name] = new_value
        _df_modified = True
        return f"Updated cell [{row_index}, '{column_name}']: '{old_value}' → '{new_value}'."
    except Exception as e:
        return f"Error updating cell: {str(e)}"


@tool("Search Data")
def search_data(search_term: str) -> str:
    """Search for a value across all columns in the spreadsheet.
    Args:
        search_term: The value to search for (case-insensitive partial match)
    """
    global _active_df
    if _active_df is None:
        return "No sheet loaded."
    try:
        mask = _active_df.apply(
            lambda col: col.astype(str).str.contains(search_term, case=False, na=False)
        ).any(axis=1)
        results = _active_df[mask]
        if len(results) == 0:
            return f"No results found for '{search_term}'."
        return f"Found {len(results)} matching row(s):\n{results.to_string()}"
    except Exception as e:
        return f"Error searching: {str(e)}"


import io
import sys

@tool("Run Python Script")
def run_python_script(script: str) -> str:
    """Execute a Python script with access to the DataFrame for custom analysis or data generation.
    The DataFrame is available as the variable 'df'. You MUST use this tool to add bulk rows or create datasets.
    If you modify the 'df', be sure to save it (e.g., df.loc[len(df)] = ... or df = pd.concat([...])).
    NOTE: Pandas 2.0+ is installed. Do NOT use df.append() as it is deprecated. Use pd.concat() instead.
    
    Args:
        script: Python code to execute. The DataFrame is available as 'df'.
    """
    global _active_df, _df_modified
    if _active_df is None:
        return "No sheet loaded."
    
    try:
        old_stdout = sys.stdout
        sys.stdout = io.StringIO()
        
        local_vars = {
            "df": _active_df,
            "pd": pd,
        }
        
        exec(script, globals(), local_vars)
        
        # Crucial: if the script re-assigned the local 'df' variable completely, we must harvest it back out!
        _active_df = local_vars.get("df", _active_df)
        
        output = sys.stdout.getvalue()
        sys.stdout = old_stdout
        
        _df_modified = True
        return f"Python script executed successfully.\nOutput:\n{output}"
    except Exception as e:
        sys.stdout = old_stdout
        return f"Error executing Python script:\n{traceback.format_exc()}"


# ═══════════════════════════════════════════
# AGENT & CREW
# ═══════════════════════════════════════════

ALL_TOOLS = [
    view_sheet, add_row, add_column, delete_row, delete_column,
    rename_column, filter_data, sort_data, fill_missing, update_cell,
    search_data, run_python_script
]

@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=10, max=65),
    reraise=True
)
def run_data_agent(query: str, df: pd.DataFrame, model: str = "ollama/qwen2.5:7b") -> dict:
    """
    Run the Data Manager agent on a user query with exponential backoff for rate limits.
    Returns: { "response": str, "df": pd.DataFrame, "modified": bool }
    """
    set_active_df(df)
    
    # Use OpenAI compatible endpoint for strict tool-calling schema validation
    local_llm = LLM(
        model=model.replace("ollama/", "openai/"),
        base_url="http://localhost:11434/v1",
        api_key="ollama"
    )

    agent = Agent(
        role="Data Manager",
        goal="Help the user manage and modify their spreadsheet data. Perform CRUD operations as requested.",
        backstory=(
            "You are an expert data manager who specializes in spreadsheet operations. "
            "You can view, add, delete, rename, filter, sort, and update data in the sheet. "
            "For adding multiple columns or rows, ALWAYS use the `run_python_script` tool to execute a Python script that applies the changes in one go. "
            "Execute operations efficiently. Only view the sheet if you absolutely need to know the data structure first. "
            "Be precise and confirm what changes you made."
        ),
        tools=ALL_TOOLS,
        verbose=False,
        max_iter=3,
        llm=local_llm,
    )

    task = Task(
        description=(
            f"The user wants to perform the following operation on their spreadsheet:\n\n"
            f"\"{query}\"\n\n"
            f"CRITICAL: If the user asks to create a dataset, create columns, or add multiple rows of data, "
            f"YOU MUST EXECUTE the `run_python_script` tool ONCE with a pandas script that does all the bulk operations at once. "
            f"DO NOT try to execute `add_column` or `add_row` multiple times. "
            f"When adding rows to an existing dataframe, ENSURE you use the EXACT same column names as the existing `df` when creating the new DataFrame to concatenate. "
            f"Example: `new_data = pd.DataFrame(data_array, columns=df.columns); df = pd.concat([df, new_data], ignore_index=True)`"
            f"You are strictly forbidden from just printing out a Markdown table and claiming you added data. "
            f"Perform the requested operation using the appropriate tools. "
            f"Finally, confirm exactly which tools you successfully called and show a brief summary."
        ),
        expected_output="A clear confirmation of what tools were executed and the exact changes made to the data.",
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
    # We must explicitly raise an exception so tenacity knows to retry.
    if "RESOURCE_EXHAUSTED" in result_str or "429" in result_str or "exceeded your current quota" in result_str.lower():
        raise Exception(f"Rate limited by LLM provider: {result_str}")

    return {
        "response": result_str,
        "df": get_active_df(),
        "modified": was_modified(),
    }
