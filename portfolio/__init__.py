from flask import Flask
from flask_sqlalchemy import SQLAlchemy 
from flask_mail import Mail
import os
import logging

logging.basicConfig(filename='error.log', level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__, instance_relative_config=True)

import re

def first_words(html_content, word_count=200):
    text = re.sub(r'<[^>]+>', ' ', html_content)
    text = re.sub(r'\s+', ' ', text).strip()
    words = text.split()
    if len(words) <= word_count:
        return text
    return ' '.join(words[:word_count]) + '...'

app.jinja_env.filters['first_words'] = first_words



# Load the config
app.config.from_pyfile('config.py', silent=False)

# Initialize extensions
db = SQLAlchemy(app)
mail = Mail(app)

# Import models
from portfolio import models

# Import routes
from portfolio import userroute
