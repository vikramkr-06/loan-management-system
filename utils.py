import pandas as pd
from datetime import datetime
from models import get_db_connection
from config import Config

def allowed_file(filename, file_type='excel'):
    """Check if file extension is allowed"""
    if file_type == 'document':
        allowed_extensions = Config.ALLOWED_DOCUMENT_EXTENSIONS
    else:
        allowed_extensions = Config.ALLOWED_EXTENSIONS
    
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_required_documents(user):
    """Get list of required documents based on user data"""
    required_docs = [
        'Aadhar Card',
        'PAN Card',
        'Salary Slip 1',
        'Salary Slip 2', 
        'Salary Slip 3',
        'Form 16 Part A',
        'Form 16 Part B',
        'Bank Statement 1',
        'Bank Statement 2',
        'Bank Statement 3',
        'Bank Statement 4',
        'Bank Statement 5',
        'Bank Statement 6'
    ]
    
    # Check if job tenure is less than 3 years
    try:
        if user['job_since']:
            # Simple check - if job_since contains a year less than 3 years ago
            current_year = datetime.now().year
            job_year = int(user['job_since'].split('-')[-1]) if '-' in user['job_since'] else int(user['job_since'])
            if current_year - job_year < 3:
                required_docs.extend(['Appointment Letter', 'Resume'])
    except (ValueError, TypeError):
        # If we can't parse the date, include the extra documents to be safe
        required_docs.extend(['Appointment Letter', 'Resume'])
    
    # Add co-applicant documents if applicable
    if user['has_co_applicant']:
        required_docs.extend([
            'Co-Applicant Aadhar Card',
            'Co-Applicant PAN Card'
        ])
    
    return required_docs

def get_uploaded_documents(user_id):
    """Get all uploaded documents for a user"""
    conn = get_db_connection()
    documents = conn.execute(
        'SELECT * FROM user_documents WHERE user_id = ? ORDER BY document_type, upload_date DESC',
        (user_id,)
    ).fetchall()
    conn.close()
    return documents

def get_document_status(user_id, user_data):
    """Get status of required vs uploaded documents"""
    required = get_required_documents(user_data)
    uploaded = get_uploaded_documents(user_id)
    
    uploaded_types = [doc['document_type'] for doc in uploaded]
    
    status = {}
    for doc_type in required:
        status[doc_type] = doc_type in uploaded_types
    
    return status

def validate_excel_columns(df):
    """Validate that Excel file has required columns"""
    required_columns = ['Applicant Name', 'Email ID', 'Loan Amount', 'Tenure']
    missing_required = [col for col in required_columns if col not in df.columns]
    
    if missing_required:
        return False, f"Missing required columns: {', '.join(missing_required)}"
    
    return True, ""

def map_excel_to_db(row):
    """Map Excel column names to database column names"""
    mapping = {
        # Applicant Details
        'Applicant Name': 'applicant_name',
        'Applicant Spouse Name': 'applicant_spouse_name',
        'Applicant Mother Name': 'applicant_mother_name',
        'Current Address': 'current_address',
        'Mobile No': 'mobile_no',
        'Email ID': 'email_id',
        'Children': 'children',
        'Qualification': 'qualification',
        'Office Address': 'office_address',
        'Office Landline No': 'office_landline',
        'Official Email ID': 'official_email_id',
        'Job Since': 'job_since',
        'Total Experience': 'total_experience',
        'Department': 'department',
        'Designation': 'designation',
        'Loan Amount': 'loan_amount',
        'Tenure': 'tenure',
        'Investment Details': 'investment_details',
        'Property Address': 'property_address',
        'Type': 'property_type',
        'Property Pincode': 'property_pincode',
        'Property Carpet Area': 'property_carpet_area',
        'Sale Deed Amount': 'sale_deed_amount',
        # Reference 1
        'Reference 1 Name': 'ref1_name',
        'Reference 1 Mobile Number': 'ref1_mobile',
        'Reference 1 Email ID': 'ref1_email',
        'Reference 1 Address': 'ref1_address',
        # Reference 2
        'Reference 2 Name': 'ref2_name',
        'Reference 2 Mobile Number': 'ref2_mobile',
        'Reference 2 Email ID': 'ref2_email',
        'Reference 2 Address': 'ref2_address',
        # Co-Applicant
        'Considering Co-Applicant Income': 'has_co_applicant',
        'Co-Applicant Name': 'co_applicant_name',
        'Co-Applicant Spouse Name': 'co_applicant_spouse_name',
        'Co-Applicant Mother Name': 'co_applicant_mother_name',
        'Co-Applicant Mobile Number': 'co_applicant_mobile',
        'Co-Applicant Current Address': 'co_applicant_address',
        'Co-Applicant Email ID': 'co_applicant_email',
        'Co-Applicant Qualification': 'co_applicant_qualification'
    }
    
    db_data = {}
    for excel_col, db_col in mapping.items():
        if excel_col in row:
            value = row[excel_col]
            # Handle boolean conversion for co-applicant checkbox
            if db_col == 'has_co_applicant':
                value = bool(value) if pd.notna(value) else False
            # Handle numeric conversions
            elif db_col in ['loan_amount', 'sale_deed_amount']:
                value = float(value) if pd.notna(value) else 0.0
            elif db_col == 'tenure':
                value = int(value) if pd.notna(value) else 0
            # Handle text conversions
            else:
                value = str(value) if pd.notna(value) else ''
            
            db_data[db_col] = value
    
    return db_data

def analyze_user_data():
    """
    Analyze all users in the database and return comprehensive analytics
    """
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users').fetchall()
    
    total_users = len(users)
    
    # Initialize counters
    users_with_full_details = 0
    users_with_pending_fields = 0
    users_with_documents_pending = 0
    users_with_coapplicant_pending = 0
    
    # Define required fields for completeness check
    required_fields = [
        'applicant_name', 'email_id', 'mobile_no', 'current_address',
        'qualification', 'department', 'designation', 'loan_amount', 'tenure',
        'property_address', 'property_type'
    ]
    
    for user in users:
        # Check field completeness
        is_complete = True
        for field in required_fields:
            if not user[field]:
                is_complete = False
                break
        
        if is_complete:
            users_with_full_details += 1
        else:
            users_with_pending_fields += 1
        
        # Check document completeness
        document_status = get_document_status(user['id'], user)
        required_doc_count = len(document_status)
        uploaded_doc_count = sum(1 for status in document_status.values() if status)
        
        if uploaded_doc_count < required_doc_count:
            users_with_documents_pending += 1
        
        # Check co-applicant completeness
        if user['has_co_applicant']:
            co_applicant_fields = [
                'co_applicant_name', 'co_applicant_mobile', 
                'co_applicant_email', 'co_applicant_address'
            ]
            co_applicant_complete = all(user[field] for field in co_applicant_fields)
            if not co_applicant_complete:
                users_with_coapplicant_pending += 1
    
    conn.close()
    
    # Calculate percentages
    analytics = {
        'total_users': total_users,
        'users_with_full_details': users_with_full_details,
        'users_with_pending_fields': users_with_pending_fields,
        'users_with_documents_pending': users_with_documents_pending,
        'users_with_coapplicant_pending': users_with_coapplicant_pending,
        'percent_full_details': round((users_with_full_details / total_users * 100) if total_users > 0 else 0, 1),
        'percent_pending_fields': round((users_with_pending_fields / total_users * 100) if total_users > 0 else 0, 1),
        'percent_documents_pending': round((users_with_documents_pending / total_users * 100) if total_users > 0 else 0, 1),
        'percent_coapplicant_pending': round((users_with_coapplicant_pending / total_users * 100) if total_users > 0 else 0, 1)
    }
    
    return analytics

def get_user_completeness_score(user_id):
    """Calculate completeness score for a specific user (0-100)"""
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    
    if not user:
        return 0
    
    # Field completeness (70% weight)
    required_fields = [
        'applicant_name', 'email_id', 'mobile_no', 'current_address',
        'qualification', 'department', 'designation', 'loan_amount', 'tenure',
        'property_address', 'property_type', 'office_address', 'total_experience'
    ]
    
    field_score = 0
    for field in required_fields:
        if user[field]:
            field_score += 1
    
    field_percentage = (field_score / len(required_fields)) * 70
    
    # Document completeness (30% weight)
    document_status = get_document_status(user_id, user)
    required_doc_count = len(document_status)
    uploaded_doc_count = sum(1 for status in document_status.values() if status)
    
    document_percentage = (uploaded_doc_count / required_doc_count) * 30 if required_doc_count > 0 else 30
    
    total_score = round(field_percentage + document_percentage)
    
    conn.close()
    return min(total_score, 100)