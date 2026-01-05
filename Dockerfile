FROM python:3.9-slim-buster

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Upgrade pip
RUN pip install --upgrade pip

# Create a script to activate the virtual environment
RUN echo 'source /app/.venv/bin/activate' >> /etc/bash.bashrc

CMD ["tail", "-f", "/dev/null"]