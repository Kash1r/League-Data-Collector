from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="league-data-collector",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A tool to collect and analyze League of Legends match data using the Riot Games API",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/league-data-collector",
    packages=find_packages(),
    package_data={
        'league_data_collector': ['*.py', '*.json'],
    },
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.25.1",
        "pandas>=1.2.0",
        "python-dotenv>=0.15.0",
        "ratelimit>=2.2.1",
        "python-dateutil>=2.8.1",
        "pydantic>=1.8.0",
        "SQLAlchemy>=1.4.0",
        "alembic>=1.7.0",
    ],
    entry_points={
        'console_scripts': [
            'league-data-collector=league_data_collector.cli:main',
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: End Users/Desktop",
        "Topic :: Games/Entertainment",
        "Topic :: Games/Entertainment :: Real Time Strategy",
        "Topic :: Utilities",
    ],
)
