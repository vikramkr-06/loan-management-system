import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Config:
    SECRET_KEY = 'your_secret_key_here_for_production_change_this'
    UPLOAD_FOLDER = 'uploads'
    DOCUMENT_UPLOAD_FOLDER = 'user_documents'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'xlsx', 'xls'}
    ALLOWED_DOCUMENT_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
    DATABASE = 'users.db'
    
    # Gemini AI Configuration
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'your_gemini_api_key_here')
    
    # Loan Eligibility Rules
    SALARIED_FOIR_MAX = 0.60  # 60%
    SELF_EMPLOYED_FOIR_MAX = 0.90  # 90%
    MAX_AGE_SALARIED = 60
    MAX_AGE_SELF_EMPLOYED = 70
    MAX_TENURE = 30  # years
    LTV_THRESHOLD = 0.75  # 75% LTV max
    
    # AI Analysis Settings
    AUTO_ANALYSIS_ENABLED = True
    AI_RETRY_ATTEMPTS = 2  # Reduced from 3 to avoid excessive retries
    AI_TIMEOUT_SECONDS = 30
    AI_RATE_LIMIT_DELAY = 1  # seconds between API calls

    # Create upload directories if they don't exist
    for folder in [UPLOAD_FOLDER, DOCUMENT_UPLOAD_FOLDER]:
        if not os.path.exists(folder):
            os.makedirs(folder)
    
    # Create logs directory
    LOGS_FOLDER = 'logs'
    if not os.path.exists(LOGS_FOLDER):
        os.makedirs(LOGS_FOLDER)