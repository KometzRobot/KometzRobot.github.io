#!/usr/bin/env python3
"""
Resume & Cover Letter Builder — Professional Gig Product
Generates professional resumes and cover letters in multiple formats.
Zero external dependencies (outputs HTML that can be saved as PDF).
Built by KometzRobot / Meridian AI

Usage:
  python3 resume-builder.py --input profile.json --template modern --output resume.html
  python3 resume-builder.py --cover-letter --company "Acme Corp" --role "Software Engineer" --input profile.json
"""

import argparse
import json
import os
from datetime import datetime


SAMPLE_PROFILE = {
    "name": "John Smith",
    "title": "Software Engineer",
    "email": "john@example.com",
    "phone": "+1 (555) 123-4567",
    "location": "New York, NY",
    "website": "https://johnsmith.dev",
    "linkedin": "linkedin.com/in/johnsmith",
    "summary": "Experienced software engineer with 5+ years building scalable web applications. Passionate about clean code, user experience, and mentoring junior developers.",
    "experience": [
        {
            "company": "Tech Corp",
            "role": "Senior Software Engineer",
            "dates": "2022 - Present",
            "bullets": [
                "Led migration of monolith to microservices, reducing deployment time by 80%",
                "Mentored team of 4 junior developers through weekly code reviews",
                "Implemented CI/CD pipeline reducing bug escape rate by 60%"
            ]
        },
        {
            "company": "StartupXYZ",
            "role": "Full Stack Developer",
            "dates": "2019 - 2022",
            "bullets": [
                "Built customer-facing dashboard serving 50K+ daily users",
                "Designed RESTful API consumed by mobile and web clients",
                "Reduced page load time from 3.2s to 0.8s through optimization"
            ]
        }
    ],
    "education": [
        {
            "school": "State University",
            "degree": "B.S. Computer Science",
            "dates": "2015 - 2019",
            "details": "GPA: 3.8/4.0, Dean's List"
        }
    ],
    "skills": ["Python", "JavaScript", "React", "Node.js", "PostgreSQL", "AWS", "Docker", "Git"],
    "certifications": ["AWS Solutions Architect Associate", "Google Cloud Professional"],
    "languages": ["English (Native)", "Spanish (Conversational)"]
}


def generate_modern_resume(profile):
    """Generate a modern, clean resume in HTML."""
    skills_html = ''.join(f'<span class="skill">{s}</span>' for s in profile.get('skills', []))

    experience_html = ''
    for exp in profile.get('experience', []):
        bullets = ''.join(f'<li>{b}</li>' for b in exp.get('bullets', []))
        experience_html += f'''
        <div class="entry">
            <div class="entry-header">
                <div><strong>{exp["role"]}</strong> at {exp["company"]}</div>
                <div class="date">{exp["dates"]}</div>
            </div>
            <ul>{bullets}</ul>
        </div>'''

    education_html = ''
    for edu in profile.get('education', []):
        education_html += f'''
        <div class="entry">
            <div class="entry-header">
                <div><strong>{edu["degree"]}</strong> — {edu["school"]}</div>
                <div class="date">{edu["dates"]}</div>
            </div>
            <p>{edu.get("details", "")}</p>
        </div>'''

    certs_html = ''
    if profile.get('certifications'):
        certs_html = '<h2>Certifications</h2><ul>' + ''.join(f'<li>{c}</li>' for c in profile['certifications']) + '</ul>'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{profile["name"]} - Resume</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #333; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 40px; }}
    .header {{ text-align: center; margin-bottom: 30px; border-bottom: 2px solid #2c3e50; padding-bottom: 20px; }}
    .header h1 {{ font-size: 28px; color: #2c3e50; margin-bottom: 5px; }}
    .header .title {{ font-size: 16px; color: #7f8c8d; margin-bottom: 10px; }}
    .contact {{ font-size: 13px; color: #555; }}
    .contact span {{ margin: 0 8px; }}
    h2 {{ font-size: 16px; color: #2c3e50; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; margin: 25px 0 15px; }}
    .summary {{ font-size: 14px; color: #555; margin-bottom: 10px; }}
    .entry {{ margin-bottom: 15px; }}
    .entry-header {{ display: flex; justify-content: space-between; align-items: baseline; }}
    .date {{ color: #7f8c8d; font-size: 13px; }}
    ul {{ margin: 5px 0 0 20px; font-size: 14px; }}
    li {{ margin-bottom: 3px; }}
    .skills {{ display: flex; flex-wrap: wrap; gap: 8px; }}
    .skill {{ background: #ecf0f1; color: #2c3e50; padding: 4px 12px; border-radius: 3px; font-size: 13px; }}
    @media print {{ body {{ padding: 20px; }} }}
</style>
</head>
<body>
    <div class="header">
        <h1>{profile["name"]}</h1>
        <div class="title">{profile.get("title", "")}</div>
        <div class="contact">
            <span>{profile.get("email", "")}</span>
            <span>{profile.get("phone", "")}</span>
            <span>{profile.get("location", "")}</span>
        </div>
    </div>

    <h2>Summary</h2>
    <p class="summary">{profile.get("summary", "")}</p>

    <h2>Experience</h2>
    {experience_html}

    <h2>Education</h2>
    {education_html}

    <h2>Skills</h2>
    <div class="skills">{skills_html}</div>

    {certs_html}
</body>
</html>'''


def generate_minimal_resume(profile):
    """Generate a minimal, text-focused resume."""
    lines = []
    lines.append(f"{'=' * 60}")
    lines.append(f"{profile['name'].upper()}")
    lines.append(f"{profile.get('title', '')}")
    lines.append(f"{profile.get('email', '')} | {profile.get('phone', '')} | {profile.get('location', '')}")
    lines.append(f"{'=' * 60}")
    lines.append('')

    lines.append('SUMMARY')
    lines.append('-' * 40)
    lines.append(profile.get('summary', ''))
    lines.append('')

    lines.append('EXPERIENCE')
    lines.append('-' * 40)
    for exp in profile.get('experience', []):
        lines.append(f"{exp['role']} — {exp['company']} ({exp['dates']})")
        for bullet in exp.get('bullets', []):
            lines.append(f"  * {bullet}")
        lines.append('')

    lines.append('EDUCATION')
    lines.append('-' * 40)
    for edu in profile.get('education', []):
        lines.append(f"{edu['degree']} — {edu['school']} ({edu['dates']})")
        if edu.get('details'):
            lines.append(f"  {edu['details']}")
        lines.append('')

    lines.append('SKILLS')
    lines.append('-' * 40)
    lines.append(', '.join(profile.get('skills', [])))

    return '\n'.join(lines)


def generate_cover_letter(profile, company, role, highlights=None):
    """Generate a professional cover letter."""
    name = profile['name']
    title = profile.get('title', 'professional')

    # Pick top experience
    top_exp = profile.get('experience', [{}])[0] if profile.get('experience') else {}
    top_bullet = top_exp.get('bullets', ['delivered impactful results'])[0] if top_exp.get('bullets') else 'delivered impactful results'

    skills_list = ', '.join(profile.get('skills', [])[:5])

    letter = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {role} position at {company}. As a {title} with expertise in {skills_list}, I am excited about the opportunity to contribute to your team.

In my current role as {top_exp.get('role', title)} at {top_exp.get('company', 'my current organization')}, I have {top_bullet.lower()}. This experience has honed my ability to deliver high-quality results in fast-paced environments.

What draws me to {company} is the opportunity to apply my skills in a meaningful way while continuing to grow professionally. I am particularly excited about the chance to work on challenging problems alongside talented colleagues.

Key qualifications I bring to this role:
"""

    for exp in profile.get('experience', [])[:2]:
        if exp.get('bullets'):
            letter += f"- {exp['bullets'][0]}\n"

    if highlights:
        for h in highlights:
            letter += f"- {h}\n"

    letter += f"""
I would welcome the opportunity to discuss how my background aligns with {company}'s goals. Thank you for considering my application.

Best regards,
{name}
{profile.get('email', '')}
{profile.get('phone', '')}"""

    return letter


def create_sample_profile(output):
    """Create a sample profile JSON."""
    with open(output, 'w') as f:
        json.dump(SAMPLE_PROFILE, f, indent=2)
    print(f"Sample profile saved to {output}")
    print("Edit this file with your information, then run:")
    print(f"  python3 resume-builder.py --input {output} --output resume.html")


def main():
    parser = argparse.ArgumentParser(description='Resume & Cover Letter Builder')
    parser.add_argument('--input', help='Profile JSON file')
    parser.add_argument('--output', help='Output file')
    parser.add_argument('--template', choices=['modern', 'minimal'], default='modern')
    parser.add_argument('--cover-letter', action='store_true', help='Generate cover letter')
    parser.add_argument('--company', help='Company name for cover letter')
    parser.add_argument('--role', help='Role for cover letter')
    parser.add_argument('--sample', action='store_true', help='Create sample profile')

    args = parser.parse_args()

    if args.sample:
        create_sample_profile(args.output or 'sample-profile.json')
        return

    if not args.input:
        print("Error: --input required (JSON profile file)")
        print("Use --sample to create a template profile")
        return

    with open(args.input, 'r') as f:
        profile = json.load(f)

    if args.cover_letter:
        if not args.company or not args.role:
            print("Error: --company and --role required for cover letter")
            return
        content = generate_cover_letter(profile, args.company, args.role)
        if args.output:
            with open(args.output, 'w') as f:
                f.write(content)
            print(f"Cover letter saved to {args.output}")
        else:
            print(content)
    else:
        if args.template == 'modern':
            content = generate_modern_resume(profile)
        else:
            content = generate_minimal_resume(profile)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(content)
            print(f"Resume saved to {args.output}")
            if args.output.endswith('.html'):
                print("Open in browser and print to PDF for final version")
        else:
            print(content)


if __name__ == '__main__':
    main()
