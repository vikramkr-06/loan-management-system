import sqlite3
from config import Config

def get_db_connection():
    conn = sqlite3.connect(Config.DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize database with all required tables"""
    # Create users table
    create_users_table()
    
    # Create documents table
    create_documents_table()
    
    # Create or update analysis table
    create_analysis_table()
    
    # Run migration for existing tables
    migrate_analysis_table()

def create_users_table():
    """Create the users table with Version 2 schema"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            -- Applicant Details
            applicant_name TEXT NOT NULL,
            applicant_spouse_name TEXT,
            applicant_mother_name TEXT,
            current_address TEXT,
            mobile_no TEXT,
            email_id TEXT UNIQUE NOT NULL,
            children TEXT,
            qualification TEXT,
            office_address TEXT,
            office_landline TEXT,
            official_email_id TEXT,
            job_since TEXT,
            total_experience TEXT,
            department TEXT,
            designation TEXT,
            loan_amount REAL NOT NULL,
            tenure INTEGER NOT NULL,
            investment_details TEXT,
            property_address TEXT,
            property_type TEXT,
            property_pincode TEXT,
            property_carpet_area TEXT,
            sale_deed_amount REAL,
            -- Reference 1
            ref1_name TEXT,
            ref1_mobile TEXT,
            ref1_email TEXT,
            ref1_address TEXT,
            -- Reference 2
            ref2_name TEXT,
            ref2_mobile TEXT,
            ref2_email TEXT,
            ref2_address TEXT,
            -- Co-Applicant Details
            has_co_applicant BOOLEAN DEFAULT FALSE,
            co_applicant_name TEXT,
            co_applicant_spouse_name TEXT,
            co_applicant_mother_name TEXT,
            co_applicant_mobile TEXT,
            co_applicant_address TEXT,
            co_applicant_email TEXT,
            co_applicant_qualification TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def create_documents_table():
    """Create the user_documents table"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            document_type TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

def create_analysis_table():
    """Create the user_analysis table for AI results"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Drop and recreate the table to ensure all columns exist
    cursor.execute('DROP TABLE IF EXISTS user_analysis')
    
    cursor.execute('''
        CREATE TABLE user_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            eligibility_status TEXT DEFAULT 'Pending',
            foir_used REAL,
            ltv_used REAL,
            ai_summary TEXT,
            ai_queries TEXT,
            missing_docs TEXT,
            risk_level TEXT,
            recommendation TEXT,
            analysis_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            retry_count INTEGER DEFAULT 0,
            last_error TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
        )
    ''')
    conn.commit()
    conn.close()

def get_user_analysis(user_id):
    """Get the latest analysis for a user as dictionary"""
    conn = get_db_connection()
    analysis = conn.execute(
        'SELECT * FROM user_analysis WHERE user_id = ? ORDER BY analysis_date DESC LIMIT 1',
        (user_id,)
    ).fetchone()
    conn.close()
    
    # Convert to dictionary if analysis exists
    return dict(analysis) if analysis else None

def save_analysis_result(user_id, eligibility_status, ai_summary, ai_queries, 
                        foir=None, ltv=None, missing_docs=None, risk_level=None, 
                        recommendation=None, retry_count=0, last_error=None):
    """Save AI analysis result to database"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if analysis already exists
    existing = cursor.execute(
        'SELECT id FROM user_analysis WHERE user_id = ?', (user_id,)
    ).fetchone()
    
    if existing:
        # Update existing analysis
        cursor.execute('''
            UPDATE user_analysis 
            SET eligibility_status=?, foir_used=?, ltv_used=?, ai_summary=?, 
                ai_queries=?, missing_docs=?, risk_level=?, recommendation=?,
                analysis_date=CURRENT_TIMESTAMP, retry_count=?, last_error=?
            WHERE user_id=?
        ''', (eligibility_status, foir, ltv, ai_summary, ai_queries, 
              missing_docs, risk_level, recommendation, retry_count, last_error, user_id))
    else:
        # Insert new analysis
        cursor.execute('''
            INSERT INTO user_analysis 
            (user_id, eligibility_status, foir_used, ltv_used, ai_summary, 
             ai_queries, missing_docs, risk_level, recommendation, retry_count, last_error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, eligibility_status, foir, ltv, ai_summary, ai_queries, 
              missing_docs, risk_level, recommendation, retry_count, last_error))
    
    conn.commit()
    conn.close()

def update_analysis_error(user_id, error_message, retry_count):
    """Update analysis with error information"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE user_analysis 
        SET eligibility_status=?, last_error=?, retry_count=?, analysis_date=CURRENT_TIMESTAMP
        WHERE user_id=?
    ''', ('AI Analysis Failed', error_message, retry_count, user_id))
    
    conn.commit()
    conn.close()
    
    print(f"Analysis failed for user {user_id}: {error_message}")

def get_analysis_stats():
    """Get statistics for dashboard"""
    conn = get_db_connection()
    
    stats = conn.execute('''
        SELECT 
            COUNT(*) as total_users,
            SUM(CASE WHEN eligibility_status = 'Eligible' THEN 1 ELSE 0 END) as eligible_users,
            SUM(CASE WHEN eligibility_status = 'Not Eligible' THEN 1 ELSE 0 END) as not_eligible_users,
            SUM(CASE WHEN eligibility_status = 'Conditional' THEN 1 ELSE 0 END) as conditional_users,
            SUM(CASE WHEN eligibility_status = 'Pending' OR eligibility_status IS NULL THEN 1 ELSE 0 END) as pending_users,
            SUM(CASE WHEN eligibility_status = 'AI Analysis Failed' THEN 1 ELSE 0 END) as failed_users
        FROM (
            SELECT u.id, 
                   COALESCE((SELECT eligibility_status FROM user_analysis 
                            WHERE user_id = u.id 
                            ORDER BY analysis_date DESC LIMIT 1), 'Pending') as eligibility_status
            FROM users u
        )
    ''').fetchone()
    
    conn.close()
    return dict(stats) if stats else {
        'total_users': 0,
        'eligible_users': 0,
        'not_eligible_users': 0,
        'conditional_users': 0,
        'pending_users': 0,
        'failed_users': 0
    }

def get_users_for_bulk_analysis(limit=10):
    """Get users that need AI analysis"""
    conn = get_db_connection()
    
    try:
        users = conn.execute('''
            SELECT u.id, u.applicant_name, u.email_id
            FROM users u
            LEFT JOIN user_analysis ua ON u.id = ua.user_id 
            WHERE ua.id IS NULL 
               OR ua.eligibility_status IN ('Pending', 'AI Analysis Failed')
               OR (ua.retry_count IS NULL OR ua.retry_count < ?)
            ORDER BY u.id DESC
            LIMIT ?
        ''', (Config.AI_RETRY_ATTEMPTS, limit)).fetchall()
    except sqlite3.OperationalError as e:
        # If retry_count column doesn't exist yet, use simpler query
        print(f"Using fallback query due to: {e}")
        users = conn.execute('''
            SELECT u.id, u.applicant_name, u.email_id
            FROM users u
            LEFT JOIN user_analysis ua ON u.id = ua.user_id 
            WHERE ua.id IS NULL 
               OR ua.eligibility_status IN ('Pending', 'AI Analysis Failed')
            ORDER BY u.id DESC
            LIMIT ?
        ''', (limit,)).fetchall()
    
    conn.close()
    return users

def check_table_schema():
    """Check if the users table has the correct schema"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Get table info
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    
    # Required columns
    required_columns = [
        'applicant_name', 'applicant_spouse_name', 'applicant_mother_name',
        'current_address', 'mobile_no', 'email_id', 'children', 'qualification',
        'office_address', 'office_landline', 'official_email_id', 'job_since',
        'total_experience', 'department', 'designation', 'loan_amount', 'tenure',
        'investment_details', 'property_address', 'property_type', 'property_pincode',
        'property_carpet_area', 'sale_deed_amount', 'ref1_name', 'ref1_mobile',
        'ref1_email', 'ref1_address', 'ref2_name', 'ref2_mobile', 'ref2_email',
        'ref2_address', 'has_co_applicant', 'co_applicant_name', 'co_applicant_spouse_name',
        'co_applicant_mother_name', 'co_applicant_mobile', 'co_applicant_address',
        'co_applicant_email', 'co_applicant_qualification'
    ]
    
    missing_columns = [col for col in required_columns if col not in columns]
    conn.close()
    
    return len(missing_columns) == 0, missing_columns

def migrate_analysis_table():
    """Safely migrate the analysis table to add missing columns"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check if table exists and get its columns
    cursor.execute("PRAGMA table_info(user_analysis)")
    existing_columns = [column[1] for column in cursor.fetchall()]
    
    # Columns to add
    columns_to_add = [
        ('foir_used', 'REAL'),
        ('ltv_used', 'REAL'), 
        ('missing_docs', 'TEXT'),
        ('risk_level', 'TEXT'),
        ('recommendation', 'TEXT'),
        ('retry_count', 'INTEGER DEFAULT 0'),
        ('last_error', 'TEXT')
    ]
    
    for column_name, column_type in columns_to_add:
        if column_name not in existing_columns:
            try:
                cursor.execute(f'ALTER TABLE user_analysis ADD COLUMN {column_name} {column_type}')
            except sqlite3.OperationalError as e:
                print(f"Column {column_name} might already exist: {e}")
    
    conn.commit()
    conn.close()
