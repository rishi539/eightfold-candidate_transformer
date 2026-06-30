"""
Skill normaliser — maps raw skill strings to canonical names.

The ``SKILL_ALIASES`` dict covers 80+ common variations.  Unknown skills
are returned cleaned-up (stripped, title-cased when all-lowercase).
"""

import logging
from typing import List

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Canonical skill alias map  (lowercase key → canonical name)
# ------------------------------------------------------------------ #
SKILL_ALIASES = {
    # --- JavaScript ecosystem ---
    "js": "JavaScript",
    "javascript": "JavaScript",
    "java script": "JavaScript",
    "ecmascript": "JavaScript",
    "es6": "JavaScript",
    "es2015": "JavaScript",
    "ts": "TypeScript",
    "typescript": "TypeScript",
    "type script": "TypeScript",
    "react": "React",
    "reactjs": "React",
    "react.js": "React",
    "react js": "React",
    "redux": "Redux",
    "next": "Next.js",
    "nextjs": "Next.js",
    "next.js": "Next.js",
    "node": "Node.js",
    "nodejs": "Node.js",
    "node.js": "Node.js",
    "node js": "Node.js",
    "express": "Express.js",
    "expressjs": "Express.js",
    "express.js": "Express.js",
    "vue": "Vue.js",
    "vuejs": "Vue.js",
    "vue.js": "Vue.js",
    "vue js": "Vue.js",
    "angular": "Angular",
    "angularjs": "Angular",
    "angular.js": "Angular",
    "angular js": "Angular",
    "svelte": "Svelte",
    "jquery": "jQuery",

    # --- Python ecosystem ---
    "py": "Python",
    "python": "Python",
    "python3": "Python",
    "python 3": "Python",
    "python2": "Python",
    "python 2": "Python",
    "django": "Django",
    "flask": "Flask",
    "fastapi": "FastAPI",
    "fast api": "FastAPI",
    "pandas": "Pandas",
    "numpy": "NumPy",
    "scipy": "SciPy",
    "matplotlib": "Matplotlib",
    "celery": "Celery",

    # --- Java / JVM ---
    "java": "Java",
    "kotlin": "Kotlin",
    "scala": "Scala",
    "spring": "Spring Boot",
    "spring boot": "Spring Boot",
    "springboot": "Spring Boot",
    "spring-boot": "Spring Boot",
    "hibernate": "Hibernate",

    # --- C / C++ / C# ---
    "c": "C",
    "cpp": "C++",
    "c++": "C++",
    "csharp": "C#",
    "c#": "C#",
    "c sharp": "C#",
    ".net": ".NET",
    "dotnet": ".NET",
    "dot net": ".NET",

    # --- Go / Rust / Swift ---
    "go": "Go",
    "golang": "Go",
    "rust": "Rust",
    "swift": "Swift",

    # --- Ruby / PHP / Perl ---
    "ruby": "Ruby",
    "rails": "Ruby on Rails",
    "ruby on rails": "Ruby on Rails",
    "ror": "Ruby on Rails",
    "php": "PHP",
    "laravel": "Laravel",
    "perl": "Perl",

    # --- Databases ---
    "sql": "SQL",
    "mysql": "MySQL",
    "postgresql": "PostgreSQL",
    "postgres": "PostgreSQL",
    "mongo": "MongoDB",
    "mongodb": "MongoDB",
    "redis": "Redis",
    "sqlite": "SQLite",
    "cassandra": "Cassandra",
    "dynamodb": "DynamoDB",
    "dynamo db": "DynamoDB",
    "elasticsearch": "Elasticsearch",
    "elastic search": "Elasticsearch",
    "neo4j": "Neo4j",

    # --- Cloud & DevOps ---
    "aws": "AWS",
    "amazon web services": "AWS",
    "gcp": "GCP",
    "google cloud": "GCP",
    "google cloud platform": "GCP",
    "azure": "Azure",
    "microsoft azure": "Azure",
    "docker": "Docker",
    "k8s": "Kubernetes",
    "kubernetes": "Kubernetes",
    "kube": "Kubernetes",
    "terraform": "Terraform",
    "ansible": "Ansible",
    "jenkins": "Jenkins",
    "ci/cd": "CI/CD",
    "cicd": "CI/CD",
    "ci cd": "CI/CD",
    "git": "Git",
    "github": "GitHub",
    "gitlab": "GitLab",
    "bitbucket": "Bitbucket",
    "linux": "Linux",
    "unix": "Unix",
    "bash": "Bash",
    "shell": "Shell Scripting",
    "shell scripting": "Shell Scripting",
    "nginx": "Nginx",
    "apache": "Apache",

    # --- Data / ML / AI ---
    "ml": "Machine Learning",
    "machine learning": "Machine Learning",
    "ai": "Artificial Intelligence",
    "artificial intelligence": "Artificial Intelligence",
    "dl": "Deep Learning",
    "deep learning": "Deep Learning",
    "nlp": "Natural Language Processing",
    "natural language processing": "Natural Language Processing",
    "cv": "Computer Vision",
    "computer vision": "Computer Vision",
    "tf": "TensorFlow",
    "tensorflow": "TensorFlow",
    "pytorch": "PyTorch",
    "torch": "PyTorch",
    "keras": "Keras",
    "scikit-learn": "Scikit-learn",
    "sklearn": "Scikit-learn",
    "scikit learn": "Scikit-learn",
    "spark": "Apache Spark",
    "pyspark": "Apache Spark",
    "apache spark": "Apache Spark",
    "hadoop": "Hadoop",
    "kafka": "Apache Kafka",
    "apache kafka": "Apache Kafka",
    "airflow": "Apache Airflow",
    "apache airflow": "Apache Airflow",
    "tableau": "Tableau",
    "power bi": "Power BI",
    "powerbi": "Power BI",
    "looker": "Looker",
    "data engineering": "Data Engineering",
    "data science": "Data Science",
    "data analysis": "Data Analysis",
    "data analytics": "Data Analytics",
    "etl": "ETL",

    # --- Web / API ---
    "html": "HTML",
    "html5": "HTML5",
    "css": "CSS",
    "css3": "CSS3",
    "sass": "Sass",
    "scss": "Sass",
    "less": "Less",
    "tailwind": "Tailwind CSS",
    "tailwindcss": "Tailwind CSS",
    "tailwind css": "Tailwind CSS",
    "bootstrap": "Bootstrap",
    "graphql": "GraphQL",
    "graph ql": "GraphQL",
    "rest": "REST API",
    "restful": "REST API",
    "rest api": "REST API",
    "restful api": "REST API",
    "grpc": "gRPC",
    "websocket": "WebSocket",
    "websockets": "WebSocket",

    # --- Mobile ---
    "react native": "React Native",
    "reactnative": "React Native",
    "flutter": "Flutter",
    "dart": "Dart",
    "ios": "iOS",
    "android": "Android",

    # --- Testing ---
    "jest": "Jest",
    "mocha": "Mocha",
    "pytest": "Pytest",
    "junit": "JUnit",
    "selenium": "Selenium",
    "cypress": "Cypress",
    "playwright": "Playwright",

    # --- Misc ---
    "agile": "Agile",
    "scrum": "Scrum",
    "jira": "Jira",
    "confluence": "Confluence",
    "figma": "Figma",
    "r": "R",
    "matlab": "MATLAB",
    "sas": "SAS",
    "excel": "Excel",
    "vba": "VBA",
    "solidity": "Solidity",
    "blockchain": "Blockchain",
    "web3": "Web3",
}


def normalize_skill(raw: str) -> str:
    """Return the canonical name for a raw skill string.

    Parameters
    ----------
    raw:
        The skill name as it appeared in the source data.

    Returns
    -------
    str
        The canonical skill name if an alias is found, otherwise
        the original string cleaned up (stripped, title-cased when
        the input is all-lowercase).
    """
    if not isinstance(raw, str):
        return str(raw)

    cleaned = raw.strip()
    if not cleaned:
        return cleaned

    lookup = cleaned.lower()

    # Direct alias hit
    if lookup in SKILL_ALIASES:
        return SKILL_ALIASES[lookup]

    # No alias — light cleanup:
    #   • if entirely lowercase, title-case it
    #   • if mixed/upper case, leave it as the user wrote it
    if cleaned == cleaned.lower():
        return cleaned.title()

    return cleaned


def deduplicate_skills(skills: List[str]) -> List[str]:
    """Remove duplicate skills after normalisation, preserving order.

    Parameters
    ----------
    skills:
        A list of raw skill strings.

    Returns
    -------
    list[str]
        De-duplicated list of canonical skill names in original
        encounter order.
    """
    seen: set[str] = set()
    result: List[str] = []
    for raw in skills:
        canonical = normalize_skill(raw)
        key = canonical.lower()
        if key not in seen:
            seen.add(key)
            result.append(canonical)
    return result
