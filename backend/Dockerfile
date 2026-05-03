# Use an official Python runtime as a parent image
FROM python:3.12

# Set the working directory in the container
WORKDIR /app

# Install system dependencies required by Django or other packages

# Copy the requirements file into the container
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire Django project into the container
COPY . /app/

# Expose the port your Django application will run on
EXPOSE 8080

# Run Django using manage.py
#CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
CMD exec gunicorn --bind :8080 --workers 1 --threads 8 --timeout 0 backend.wsgi:application