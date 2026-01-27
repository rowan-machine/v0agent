# sdk/setup.py
"""
SignalFlow SDK Package Setup

Install the SDK:
    pip install -e sdk/
    
Or for development:
    pip install -e "sdk/[dev]"
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="signalflow-sdk",
    version="0.1.0",
    author="V0Agent Team",
    author_email="team@v0agent.dev",
    description="Python SDK for SignalFlow meeting intelligence platform",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/v0agent/v0agent",
    packages=find_packages(exclude=["tests", "tests.*"]),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.10",
    install_requires=[
        "httpx>=0.24.0",
        "pydantic>=2.0.0",
    ],
    extras_require={
        "analyst": [
            "langsmith>=0.1.0",
        ],
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "respx>=0.20.0",  # For mocking httpx
        ],
    },
)
