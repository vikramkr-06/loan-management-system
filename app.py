from flask import Flask
from config import Config
from models import init_db, check_table_schema, get_user_analysis
from routes import configure_routes

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database (only at app start)
init_db()

# Verify schema
is_valid, missing = check_table_schema()
if is_valid:
    print("✓ Database schema is ready")
else:
    print(f"✗ Database schema issues: {missing}")

# Configure all routes
configure_routes(app)

@app.context_processor
def utility_processor():
    def get_user_analysis_for_template(user_id):
        return get_user_analysis(user_id)
    return dict(get_user_analysis=get_user_analysis_for_template)
