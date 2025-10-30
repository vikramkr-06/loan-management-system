from flask import Flask
from config import Config
from models import init_db, check_table_schema
from routes import configure_routes
from models import get_user_analysis

app = Flask(__name__)
app.config.from_object(Config)

# Configure all routes
configure_routes(app)

@app.context_processor
def utility_processor():
    def get_user_analysis_for_template(user_id):
        return get_user_analysis(user_id)
    return dict(get_user_analysis=get_user_analysis_for_template)

if __name__ == '__main__':
    # Initialize database with all required tables
    init_db()
    
    # Verify schema is correct
    is_valid, missing = check_table_schema()
    if is_valid:
        print("✓ Database schema is ready")
    else:
        print(f"✗ Database schema issues: {missing}")
    
    app.run(debug=True, host='127.0.0.1', port=5000)