# Resume Analyzer

Flask app to compare an uploaded resume PDF against job-required skills.

## Project structure

```
resume analyser/
├── app.py
├── requirements.txt
├── .gitignore
├── resume_analyser.py
└── resume_analyser_app/
    ├── __init__.py
    ├── web.py
    └── templates/
        └── index.html
```

## Run locally

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run:

```bash
python app.py
```

4. Open `http://127.0.0.1:5000/`.

