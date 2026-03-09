# VizData AI

## Overview

VizData AI is an intelligent spreadsheet application that seamlessly integrates data management and analytics through autonomous AI agents. Powered by CrewAI and local LLM processing, the platform offers a fully interactive, spreadsheet-inspired web interface where users can directly manipulate data or instruct AI assistants to perform complex bulk operations, data generation, and advanced visualizations.

The system is composed of two primary agentic workflows:
1. **Data Manager:** Modifies the underlying Pandas DataFrame (adding rows, columns, filtering, sorting, or generating datasets from scratch) and reflects changes in real-time on the frontend spreadsheet grid.
2. **Analytics Agent:** Analyzes the active dataset to generate insights and plots out compelling statistical charts using Matplotlib and Seaborn.

## Key Features

- **Interactive Spreadsheet UI:** A rich frontend built with Vanilla JS and CSS offering cell selection, inline editing, column/row indicators, and a modern aesthetic.
- **AI-Driven Data Generation:** Create entire datasets from scratch. The Data Manager dynamically writes and executes Pandas scripts to fulfill bulk data requests natively.
- **Local Model Support:** Fully compatible with local LLMs (like Qwen 2.5 via Ollama) to bypass API rate limits, utilizing strict API base overrides for secure and native JSON tool-calling execution.
- **Seamless Analytics:** Chat with the Analytics Agent to request distributions, scatter plots, Heatmaps, and statistical summaries, which are automatically rendered and presented back to the user interface.
- **Robust Session Management:** Multi-sheet support with in-memory DataFrame storage and CSV/XLSX file uploads.

## Technology Stack

- **Backend:** Python, FastAPI, Pandas, Matplotlib, Seaborn
- **AI Orchestration:** CrewAI, LiteLLM
- **Frontend:** HTML5, CSS3, Vanilla JavaScript

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/vizdata-ai.git
   cd vizdata-ai
   ```

2. **Set up the Environment:**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On MacOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Configuration:**
   By default, the application is configured to route AI requests to a local Ollama instance (`http://localhost:11434/v1`) using the `ollama/qwen2.5:7b` model to ensure privacy and eliminate rate limits. 
   
   If you wish to use cloud models (e.g., Gemini), you can specify your keys by creating a `.env` file in the root directory:
   ```env
   GEMINI_API_KEY=your_key_here
   ```

## Usage

1. **Start the Backend Server:**
   ```bash
   cd backend
   python main.py
   ```
   The FastAPI server will start on `http://localhost:8000`.

2. **Access the Application:**
   Open a web browser and navigate to `http://localhost:8000`. 
   
   From the homepage, you can either:
   - Upload an existing standard data file (.csv, .xlsx).
   - Click "Create with AI" to open a blank canvas and instruct the Data Manager to populate a new custom dataset.

## Architecture Notes

- **Strict Tool Parsing:** Open-source models often struggle to maintain strict JSON API outputs. VizData AI enforces strict state manipulation by injecting OpenAI base-URL API overrides, forcing the output parser to reliably intercept tool calls and invoke local Python sandbox tools.
- **Data Synchronization:** The data pipeline securely isolates executing code while ensuring that DataFrames modified by the AI are extracted from the local script sandbox and synchronized back to the global application session state before answering the user.
