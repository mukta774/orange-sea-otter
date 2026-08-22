from flask import Flask, render_template, request
from resume_analyser import ResumeAnalyzer
import html
import json
import re
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

analyzer = ResumeAnalyzer()  # No default PDF; text comes from uploaded resume per request

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024  # 10 MB upload limit


def strip_html_tags(value):
    clean = re.sub(r'<[^>]+>', ' ', value or '')
    clean = re.sub(r'\s+', ' ', clean).strip()
    return html.unescape(clean)


def fetch_job_description(company_name, job_title, job_location=''):
    search_query = f"{job_title} {company_name}".strip()
    url = f"https://remotive.com/api/remote-jobs?search={quote_plus(search_query)}"

    request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urlopen(request, timeout=20) as response:
        payload = json.loads(response.read().decode('utf-8'))

    jobs = payload.get('jobs', [])
    if not jobs:
        return None

    company_lower = company_name.lower().strip()
    location_lower = job_location.lower().strip()

    def score_job(job):
        score = 0
        current_company = (job.get('company_name') or '').lower()
        current_title = (job.get('title') or '').lower()
        current_location = (job.get('candidate_required_location') or '').lower()
        if company_lower and company_lower in current_company:
            score += 5
        if job_title.lower() in current_title:
            score += 4
        if location_lower and location_lower in current_location:
            score += 2
        return score

    best_job = max(jobs, key=score_job)
    description_text = strip_html_tags(best_job.get('description', ''))
    if not description_text:
        return None

    return {
        'description': description_text,
        'company_name': best_job.get('company_name', ''),
        'title': best_job.get('title', ''),
        'location': best_job.get('candidate_required_location', ''),
        'url': best_job.get('url', ''),
        'source': 'Remotive Jobs API',
    }


@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    error = None
    info = None
    job_fetch = None

    required_skills_raw = ''
    company_name = ''
    job_title = ''
    job_location = ''
    job_description_text = ''

    if request.method == 'POST':
        action = request.form.get('action', 'analyze_match')
        required_skills_raw = request.form.get('required_skills', '')
        company_name = request.form.get('company_name', '').strip()
        job_title = request.form.get('job_title', '').strip()
        job_location = request.form.get('job_location', '').strip()
        job_description_text = request.form.get('job_description_text', '').strip()

        if action == 'fetch_job':
            if not company_name or not job_title:
                error = "Please enter both company name and job title to fetch a job description."
            else:
                try:
                    job_fetch = fetch_job_description(company_name, job_title, job_location)
                except Exception as exc:
                    error = f"Failed to fetch job description: {exc}"
                else:
                    if not job_fetch:
                        error = "No matching job description was found."
                    else:
                        job_description_text = job_fetch['description']
                        info = "Job description fetched successfully."
                        if not required_skills_raw:
                            inferred_job_skills = analyzer.extract_skills_with_fuzzy_matching(
                                job_description_text, analyzer.common_skills_fuzzy
                            )
                            required_skills_raw = ", ".join(inferred_job_skills)

        elif action == 'analyze_match':
            uploaded_file = request.files.get('resume_pdf')
            if not uploaded_file or uploaded_file.filename == '':
                error = "Please upload a PDF resume before analyzing."
            elif not uploaded_file.filename.lower().endswith('.pdf'):
                error = "Only PDF files are supported."
            else:
                job_required_skills = [s.strip() for s in required_skills_raw.split(',') if s.strip()]
                required_skills_source = "Manual required skills"

                if not job_required_skills and job_description_text:
                    job_required_skills = analyzer.extract_skills_with_fuzzy_matching(
                        job_description_text, analyzer.common_skills_fuzzy
                    )
                    required_skills_raw = ", ".join(job_required_skills)
                    required_skills_source = "Inferred from job description text"

                if not job_required_skills:
                    error = "Please provide required skills or a job description to infer skills from."
                else:
                    resume_text = None
                    try:
                        resume_text = analyzer.extract_text_from_file(uploaded_file.stream)
                    except Exception as exc:
                        error = f"Could not read the PDF: {exc}"

                    if resume_text is not None:
                        if not resume_text.strip():
                            error = "No text could be extracted from the uploaded PDF."
                        else:
                            extracted_skills_resume = analyzer.extract_skills_with_fuzzy_matching(
                                resume_text, analyzer.common_skills_fuzzy
                            )
                            matched_required_skills = analyzer.extract_skills_with_fuzzy_matching(
                                resume_text, job_required_skills
                            )
                            matched_set = {s.lower() for s in matched_required_skills}
                            missing_required_skills = [
                                s for s in job_required_skills if s.lower() not in matched_set
                            ]
                            skill_match_score_val = analyzer.calculate_skill_match_score(
                                matched_required_skills, job_required_skills
                            )

                            education_match = re.search(analyzer.education_pattern, resume_text, re.DOTALL | re.IGNORECASE)
                            education_section_val = education_match.group(1).strip() if education_match else "Not found"

                            experience_match = re.search(analyzer.experience_pattern, resume_text, re.DOTALL | re.IGNORECASE)
                            experience_section_val = experience_match.group(1).strip() if experience_match else "Not found"

                            skill_comparison = [
                                (skill, skill.lower() in matched_set) for skill in job_required_skills
                            ]

                            results = {
                                'extracted_skills': ", ".join(extracted_skills_resume),
                                'matched_skills': ", ".join(matched_required_skills),
                                'missing_skills': ", ".join(missing_required_skills),
                                'skill_comparison': skill_comparison,
                                'skill_match_score': f"{skill_match_score_val:.2f}",
                                'required_skills_source': required_skills_source,
                                'education_section': education_section_val,
                                'experience_section': experience_section_val,
                            }

    return render_template(
        'index.html',
        results=results,
        error=error,
        info=info,
        job_fetch=job_fetch,
        required_skills_raw=required_skills_raw,
        company_name=company_name,
        job_title=job_title,
        job_location=job_location,
        job_description_text=job_description_text,
    )
