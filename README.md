# 🔍 OCR-AI

**PDF to Structured JSON Pipeline using DeepSeek OCR & OpenAI**

Transform scanned PDF documents (like inspection forms) into structured, validated JSON using local OCR powered by DeepSeek and intelligent extraction via OpenAI.

---

## ✨ Features

- **Local OCR Processing** — Uses DeepSeek OCR model via Ollama for privacy-first text extraction
- **Multi-page PDF Support** — Automatically processes all pages in a PDF
- **Structured Output** — Converts unstructured OCR text to validated Pydantic schemas
- **Batch Processing** — Drop multiple PDFs in the input folder and process them all
- **Template-aware Extraction** — Uses JSON templates to guide the extraction process

---

## 📋 Prerequisites

Before you begin, ensure you have the following installed:

- **Python 3.13+**
- **[UV](https://docs.astral.sh/uv/)** — Fast Python package manager
- **[Ollama](https://ollama.ai/)** — Local LLM runner

---

## 🚀 Getting Started

### Step 1: Install and Run DeepSeek OCR Model via Ollama

First, make sure Ollama is installed and running on your machine.

```bash
# Install Ollama (if not already installed)
# macOS
brew install ollama

# Or download from https://ollama.ai/download
```

Start the Ollama service:

```bash
ollama serve
```

Pull and run the DeepSeek OCR model:

```bash
ollama pull deepseek-ocr
```

> **Note:** Keep Ollama running in the background while using this tool.

---

### Step 2: Install Dependencies with UV

Clone the repository and install dependencies:

```bash
# Clone the repository
git clone <repository-url>
cd OCR-AI

# Install UV if you haven't already
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with pip
pip install uv

# Install project dependencies
uv sync
```

---

### Step 3: Get Your OpenAI API Key

1. Go to [OpenAI Platform](https://platform.openai.com/api-keys)
2. Sign in or create an account
3. Navigate to **API Keys** section
4. Click **"Create new secret key"**
5. Copy the generated key (starts with `sk-`)

---

### Step 4: Configure Environment Variables

Create a `.env` file in the project root:

```bash
touch .env
```

Add your OpenAI API key to the `.env` file:

```env
OPENAI_API_KEY=sk-your-api-key-here
```

> ⚠️ **Important:** Never commit your `.env` file to version control!

---

### Step 5: Run the Pipeline

Place your PDF files in the `input/` directory, then run:

```bash
uv run python main.py
```

The extracted JSON files will be saved to the `output/` directory with the naming convention `output_{filename}.json`.

---

## 📁 Project Structure

```
OCR-AI/
├── input/                    # Drop your PDF files here
│   └── *.pdf
├── output/                   # Extracted JSON outputs
│   └── output_*.json
├── templates/                # JSON templates for extraction context
│   └── inspection_template.json
├── src/
│   ├── pipeline.py           # Main orchestration
│   ├── pdf_processor.py      # PDF to image conversion
│   ├── ocr_engine.py         # DeepSeek OCR via Ollama
│   ├── json_extractor.py     # OpenAI-powered JSON extraction
│   └── schemas.py            # Pydantic models
├── main.py                   # Entry point
├── pyproject.toml            # Project dependencies
└── .env                      # Your API keys (create this)
```

---

## 🔧 How It Works

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   PDF File  │ ──▶ │  Convert to │ ──▶ │  DeepSeek   │ ──▶ │   OpenAI    │
│             │     │   Images    │     │  OCR (local)│     │  Extraction │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                                                                   │
                                                                   ▼
                                                          ┌─────────────┐
                                                          │ Structured  │
                                                          │    JSON     │
                                                          └─────────────┘
```

1. **PDF Processing** — Converts each PDF page to high-resolution images
2. **OCR Extraction** — DeepSeek OCR (running locally via Ollama) extracts text with layout preservation
3. **JSON Extraction** — OpenAI intelligently maps the OCR text to your Pydantic schema
4. **Validation** — Output is validated against the schema and saved as JSON

---

## 📝 Example Usage

**Input:** `input/sample-inspection-form.pdf`

**Output:** `output/output_sample-inspection-form.json`

```json
{
  "id": 12345,
  "name": "Move-In Inspection",
  "versions": [
    {
      "version_id": 1,
      "structure": {
        "name": "Unit Inspection",
        "sections": [...]
      }
    }
  ]
}
```

---

## 🛠️ Configuration

You can modify these settings in `main.py`:

| Variable | Description | Default |
|----------|-------------|---------|
| `INPUT_DIR` | Directory for input PDFs | `input` |
| `OUTPUT_DIR` | Directory for output JSON | `output` |
| `MODEL` | OpenAI model for extraction | `gpt-5.2` |

---

## 🐛 Troubleshooting

### Ollama not running
```
Error: Could not connect to Ollama
```
**Solution:** Make sure Ollama is running with `ollama serve`

### Model not found
```
Error: model 'deepseek-ocr' not found
```
**Solution:** Pull the model with `ollama pull deepseek-ocr`

### OpenAI API key missing
```
Error: OPENAI_API_KEY not found in .env file
```
**Solution:** Create a `.env` file with your API key (see Step 4)

---

## 📄 License

MIT License

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

