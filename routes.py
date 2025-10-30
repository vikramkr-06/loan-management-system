from flask import render_template, request, redirect, url_for, flash, send_file
import sqlite3
import pandas as pd
import os
from werkzeug.utils import secure_filename
import uuid

from models import get_db_connection, check_table_schema, get_user_analysis, get_analysis_stats, get_users_for_bulk_analysis
from utils import (
    allowed_file, get_required_documents, get_uploaded_documents, 
    get_document_status, validate_excel_columns, map_excel_to_db,
    analyze_user_data, get_user_completeness_score
)
from ai_utils import trigger_ai_analysis, trigger_bulk_analysis, analyze_loan_eligibility
from config import Config

# from mock_ai_utils import trigger_ai_analysis, trigger_bulk_analysis

def configure_routes(app):
    
    @app.route('/')
    def dashboard():
        # Get basic stats
        conn = get_db_connection()
        total_users = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        total_loan_amount = conn.execute('SELECT SUM(loan_amount) FROM users').fetchone()[0]
        total_loan_amount = total_loan_amount if total_loan_amount else 0
        
        # Get users with documents
        users_with_documents = conn.execute('''
            SELECT DISTINCT user_id FROM user_documents
        ''').fetchall()
        users_with_docs_count = len(users_with_documents)
        conn.close()
        
        # Get comprehensive analytics
        analytics = analyze_user_data()
        
        # Get AI analysis stats
        ai_stats = get_analysis_stats()
        
        return render_template('dashboard.html', 
                             total_users=total_users, 
                             total_loan_amount=total_loan_amount,
                             users_with_docs_count=users_with_docs_count,
                             analytics=analytics,
                             ai_stats=ai_stats)

    @app.route('/create_user')
    def create_user():
        return render_template('create_user.html')

    @app.route('/create_manually', methods=['GET', 'POST'])
    def create_manually():
        if request.method == 'POST':
            # Initialize variables
            new_user = None
            user_created = False

            try:
                # Applicant Details
                applicant_name = request.form['applicant_name']
                applicant_spouse_name = request.form.get('applicant_spouse_name', '')
                applicant_mother_name = request.form.get('applicant_mother_name', '')
                current_address = request.form.get('current_address', '')
                mobile_no = request.form.get('mobile_no', '')
                email_id = request.form['email_id']
                children = request.form.get('children', '')
                qualification = request.form.get('qualification', '')
                office_address = request.form.get('office_address', '')
                office_landline = request.form.get('office_landline', '')
                official_email_id = request.form.get('official_email_id', '')
                job_since = request.form.get('job_since', '')
                total_experience = request.form.get('total_experience', '')
                department = request.form.get('department', '')
                designation = request.form.get('designation', '')
                loan_amount = float(request.form['loan_amount'])
                tenure = int(request.form['tenure'])
                investment_details = request.form.get('investment_details', '')
                property_address = request.form.get('property_address', '')
                property_type = request.form.get('property_type', '')
                property_pincode = request.form.get('property_pincode', '')
                property_carpet_area = request.form.get('property_carpet_area', '')
                sale_deed_amount = float(request.form.get('sale_deed_amount', 0))
            
                # Reference 1
                ref1_name = request.form.get('ref1_name', '')
                ref1_mobile = request.form.get('ref1_mobile', '')
                ref1_email = request.form.get('ref1_email', '')
                ref1_address = request.form.get('ref1_address', '')

                # Reference 2
                ref2_name = request.form.get('ref2_name', '')
                ref2_mobile = request.form.get('ref2_mobile', '')
                ref2_email = request.form.get('ref2_email', '')
                ref2_address = request.form.get('ref2_address', '')

                # Co-Applicant Details
                has_co_applicant = 'has_co_applicant' in request.form
                co_applicant_name = request.form.get('co_applicant_name', '')
                co_applicant_spouse_name = request.form.get('co_applicant_spouse_name', '')
                co_applicant_mother_name = request.form.get('co_applicant_mother_name', '')
                co_applicant_mobile = request.form.get('co_applicant_mobile', '')
                co_applicant_address = request.form.get('co_applicant_address', '')
                co_applicant_email = request.form.get('co_applicant_email', '')
                co_applicant_qualification = request.form.get('co_applicant_qualification', '')

                conn = get_db_connection()

                try:
                    # Insert user
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO users (
                            applicant_name, applicant_spouse_name, applicant_mother_name, current_address,
                            mobile_no, email_id, children, qualification, office_address, office_landline,
                            official_email_id, job_since, total_experience, department, designation,
                            loan_amount, tenure, investment_details, property_address, property_type,
                            property_pincode, property_carpet_area, sale_deed_amount,
                            ref1_name, ref1_mobile, ref1_email, ref1_address,
                            ref2_name, ref2_mobile, ref2_email, ref2_address,
                            has_co_applicant, co_applicant_name, co_applicant_spouse_name, co_applicant_mother_name,
                            co_applicant_mobile, co_applicant_address, co_applicant_email, co_applicant_qualification
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        applicant_name, applicant_spouse_name, applicant_mother_name, current_address,
                        mobile_no, email_id, children, qualification, office_address, office_landline,
                        official_email_id, job_since, total_experience, department, designation,
                        loan_amount, tenure, investment_details, property_address, property_type,
                        property_pincode, property_carpet_area, sale_deed_amount,
                        ref1_name, ref1_mobile, ref1_email, ref1_address,
                        ref2_name, ref2_mobile, ref2_email, ref2_address,
                        has_co_applicant, co_applicant_name, co_applicant_spouse_name, co_applicant_mother_name,
                        co_applicant_mobile, co_applicant_address, co_applicant_email, co_applicant_qualification
                    ))

                    # Get the new user ID
                    new_user_id = cursor.lastrowid
                    conn.commit()
                    user_created = True

                    # Get the complete user record
                    new_user = conn.execute(
                        'SELECT * FROM users WHERE id = ?', (new_user_id,)
                    ).fetchone()

                    flash('User created successfully! AI analysis started automatically.', 'success')

                except sqlite3.IntegrityError:
                    flash('Email already exists! Please use a different email address.', 'error')
                except Exception as e:
                    flash(f'Error creating user: {str(e)}', 'error')
                finally:
                    conn.close()

            except Exception as e:
                flash(f'Form processing error: {str(e)}', 'error')

            # Trigger automatic AI analysis for the new user only if creation was successful
            if user_created and new_user:
                try:
                    trigger_ai_analysis(new_user['id'])
                except Exception as e:
                    flash(f'User created but AI analysis failed to start: {str(e)}', 'warning')

            return redirect(url_for('create_manually'))
    
        return render_template('create_manually.html')

    @app.route('/upload_excel', methods=['GET', 'POST'])
    def upload_excel():
        # Check database schema before processing upload
        is_valid_schema, missing_columns = check_table_schema()
        if not is_valid_schema:
            flash(f'Database schema is outdated. Missing columns: {", ".join(missing_columns)}. Please contact administrator.', 'error')
            return redirect(url_for('upload_excel'))
        
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file selected', 'error')
                return redirect(request.url)
            
            file = request.files['file']
            
            if file.filename == '':
                flash('No file selected', 'error')
                return redirect(request.url)
            
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(Config.UPLOAD_FOLDER, filename)
                file.save(filepath)
                
                try:
                    # Read Excel file
                    df = pd.read_excel(filepath)
                    
                    # Validate required columns
                    is_valid, error_msg = validate_excel_columns(df)
                    if not is_valid:
                        flash(error_msg, 'error')
                        return redirect(request.url)
                    
                    conn = get_db_connection()
                    success_count = 0
                    error_count = 0
                    error_details = []
                    new_user_ids = []
                    
                    for index, row in df.iterrows():
                        try:
                            # Map Excel data to database columns
                            db_data = map_excel_to_db(row)
                            
                            # Build dynamic SQL query based on available data
                            columns = []
                            placeholders = []
                            values = []
                            
                            for col, value in db_data.items():
                                columns.append(col)
                                placeholders.append('?')
                                values.append(value)
                            
                            if not columns:
                                continue
                                
                            query = f'''
                                INSERT INTO users ({', '.join(columns)})
                                VALUES ({', '.join(placeholders)})
                            '''
                            
                            cursor = conn.cursor()
                            cursor.execute(query, values)
                            new_user_id = cursor.lastrowid
                            new_user_ids.append(new_user_id)
                            success_count += 1
                            
                        except (sqlite3.IntegrityError, ValueError, KeyError) as e:
                            error_count += 1
                            error_details.append(f"Row {index + 2}: {str(e)}")
                            print(f"Error inserting row {index + 2}: {e}")
                    
                    conn.commit()
                    conn.close()
                    
                    # Trigger AI analysis for all new users
                    for user_id in new_user_ids:
                        trigger_ai_analysis(user_id)
                    
                    if success_count > 0:
                        flash(f'Successfully imported {success_count} users. AI analysis started for new users.', 'success')
                    if error_count > 0:
                        error_msg = f'{error_count} records failed to import.'
                        if error_details:
                            error_msg += ' First error: ' + error_details[0]
                        flash(error_msg, 'warning')
                    
                except Exception as e:
                    flash(f'Error processing file: {str(e)}', 'error')
                    print(f"Excel processing error: {e}")
                
                finally:
                    # Clean up uploaded file
                    if os.path.exists(filepath):
                        os.remove(filepath)
                
                return redirect(url_for('upload_excel'))
            else:
                flash('Please upload a valid Excel file (.xlsx or .xls)', 'error')
        
        return render_template('upload_excel.html')

    @app.route('/all_users')
    def all_users():
        conn = get_db_connection()
        users = conn.execute('''
            SELECT u.*, 
                   COUNT(d.id) as document_count
            FROM users u 
            LEFT JOIN user_documents d ON u.id = d.user_id 
            GROUP BY u.id 
            ORDER BY u.id DESC
        ''').fetchall()
        conn.close()
    
        # Add completeness score and AI analysis status to each user
        users_with_scores = []
        for user in users:
            # Convert sqlite3.Row to dict
            user_dict = dict(user)
            user_dict['completeness_score'] = get_user_completeness_score(user['id'])

            # Get AI analysis status
            user_analysis = get_user_analysis(user['id'])
            if user_analysis:
                # Use dictionary-style access for sqlite3.Row
                user_dict['ai_status'] = user_analysis['eligibility_status'] if 'eligibility_status' in user_analysis.keys() else 'Pending'
                user_dict['risk_level'] = user_analysis['risk_level'] if 'risk_level' in user_analysis.keys() else None
                user_dict['has_analysis'] = True
            else:
                user_dict['ai_status'] = 'Pending'
                user_dict['risk_level'] = None
                user_dict['has_analysis'] = False

            users_with_scores.append(user_dict)

        return render_template('all_users.html', users=users_with_scores)

    @app.route('/user/<int:user_id>')
    def view_user(user_id):
        """View individual user details"""
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()

        if user is None:
            flash('User not found!', 'error')
            return redirect(url_for('all_users'))

        # Get uploaded documents and document status
        uploaded_documents = get_uploaded_documents(user_id)
        document_status = get_document_status(user_id, user)
        completeness_score = get_user_completeness_score(user_id)

        # Get AI analysis status
        user_analysis = get_user_analysis(user_id)
        user_dict = dict(user)

        if user_analysis:
            analysis_dict = dict(user_analysis)
            user_dict['has_analysis'] = True
            user_dict['ai_status'] = analysis_dict.get('eligibility_status', 'Pending')
            user_dict['risk_level'] = analysis_dict.get('risk_level')
        else:
            user_dict['has_analysis'] = False
            user_dict['ai_status'] = 'Pending'
            user_dict['risk_level'] = None

        return render_template('user_details.html', 
                             user=user_dict, 
                             uploaded_documents=uploaded_documents,
                             document_status=document_status,
                             completeness_score=completeness_score,
                             user_analysis=user_analysis)

    @app.route('/user/<int:user_id>/upload_documents', methods=['GET', 'POST'])
    def upload_documents(user_id):
        """Handle document upload for a specific user"""
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        
        if user is None:
            flash('User not found!', 'error')
            return redirect(url_for('all_users'))
        
        if request.method == 'POST':
            uploaded_files = request.files.getlist('documents')
            document_types = request.form.getlist('document_types')
            
            success_count = 0
            error_count = 0
            
            for file, doc_type in zip(uploaded_files, document_types):
                if file and file.filename != '' and doc_type:
                    if allowed_file(file.filename, 'document'):
                        # Generate unique filename
                        original_filename = secure_filename(file.filename)
                        file_extension = original_filename.rsplit('.', 1)[1].lower()
                        unique_filename = f"{user_id}_{doc_type.replace(' ', '_')}_{uuid.uuid4().hex[:8]}.{file_extension}"
                        
                        # Create user-specific folder
                        user_folder = os.path.join(Config.DOCUMENT_UPLOAD_FOLDER, str(user_id))
                        if not os.path.exists(user_folder):
                            os.makedirs(user_folder)
                        
                        file_path = os.path.join(user_folder, unique_filename)
                        
                        try:
                            # Save file
                            file.save(file_path)
                            file_size = os.path.getsize(file_path)
                            
                            # Save to database
                            conn = get_db_connection()
                            conn.execute('''
                                INSERT INTO user_documents (user_id, document_type, file_name, file_path, file_size)
                                VALUES (?, ?, ?, ?, ?)
                            ''', (user_id, doc_type, original_filename, file_path, file_size))
                            conn.commit()
                            conn.close()
                            
                            success_count += 1
                            
                        except Exception as e:
                            error_count += 1
                            print(f"Error saving document: {e}")
                    else:
                        error_count += 1
                        flash(f'Invalid file type for {doc_type}. Allowed: PDF, JPG, JPEG, PNG', 'warning')
            
            if success_count > 0:
                flash(f'Successfully uploaded {success_count} document(s)!', 'success')
                # Trigger re-analysis if documents were uploaded
                trigger_ai_analysis(user_id)
            if error_count > 0:
                flash(f'Failed to upload {error_count} document(s). Please check file types and try again.', 'error')
            
            return redirect(url_for('view_user', user_id=user_id))
        
        # GET request - show upload form
        uploaded_documents = get_uploaded_documents(user_id)
        document_status = get_document_status(user_id, user)
        required_documents = get_required_documents(user)
        
        return render_template('upload_documents.html',
                             user=user,
                             uploaded_documents=uploaded_documents,
                             document_status=document_status,
                             required_documents=required_documents)

    @app.route('/download_document/<int:doc_id>')
    def download_document(doc_id):
        """Download a specific document"""
        conn = get_db_connection()
        document = conn.execute(
            'SELECT * FROM user_documents WHERE id = ?', (doc_id,)
        ).fetchone()
        conn.close()
        
        if document is None:
            flash('Document not found!', 'error')
            return redirect(url_for('all_users'))
        
        try:
            return send_file(document['file_path'], 
                            as_attachment=True, 
                            download_name=document['file_name'])
        except FileNotFoundError:
            flash('Document file not found on server!', 'error')
            return redirect(url_for('view_user', user_id=document['user_id']))

    @app.route('/delete_document/<int:doc_id>')
    def delete_document(doc_id):
        """Delete a specific document"""
        conn = get_db_connection()
        document = conn.execute(
            'SELECT * FROM user_documents WHERE id = ?', (doc_id,)
        ).fetchone()
        
        if document is None:
            flash('Document not found!', 'error')
            return redirect(url_for('all_users'))
        
        user_id = document['user_id']
        
        try:
            # Delete file from filesystem
            if os.path.exists(document['file_path']):
                os.remove(document['file_path'])
            
            # Delete record from database
            conn.execute('DELETE FROM user_documents WHERE id = ?', (doc_id,))
            conn.commit()
            flash('Document deleted successfully!', 'success')
            
        except Exception as e:
            flash(f'Error deleting document: {str(e)}', 'error')
        
        finally:
            conn.close()
        
        return redirect(url_for('view_user', user_id=user_id))

    @app.route('/user/<int:user_id>/download_all')
    def download_all_documents(user_id):
        """Download all documents for a user as zip (placeholder)"""
        flash('Bulk download feature coming soon!', 'info')
        return redirect(url_for('view_user', user_id=user_id))

    # AI Analysis Routes
    @app.route('/user/<int:user_id>/run_analysis')
    def run_analysis(user_id):
        """Run AI analysis for a user"""
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        
        if user is None:
            flash('User not found!', 'error')
            return redirect(url_for('all_users'))
        
        return render_template('run_analysis.html', user=user)

    @app.route('/user/<int:user_id>/analyze', methods=['POST'])
    def analyze_user(user_id):
        """Execute AI analysis"""
        try:
            # Run AI analysis
            analysis_result = analyze_loan_eligibility(user_id)
            
            if 'error' in analysis_result:
                flash(f'Analysis failed: {analysis_result["error"]}', 'error')
                return redirect(url_for('view_user', user_id=user_id))
            
            flash('AI analysis completed successfully!', 'success')
            return redirect(url_for('view_loan_analysis', user_id=user_id))
            
        except Exception as e:
            flash(f'Analysis error: {str(e)}', 'error')
            return redirect(url_for('view_user', user_id=user_id))

    @app.route('/user/<int:user_id>/analysis')
    def view_loan_analysis(user_id):
        """View AI analysis results"""
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        analysis = get_user_analysis(user_id)
        conn.close()
        
        if user is None:
            flash('User not found!', 'error')
            return redirect(url_for('all_users'))
        
        return render_template('loan_analysis.html', user=user, analysis=analysis)

    @app.route('/analyze_bulk')
    def analyze_bulk():
        """Analyze all pending users"""
        pending_users = get_users_for_bulk_analysis(limit=20)
        user_ids = [user['id'] for user in pending_users]
        
        if user_ids:
            trigger_bulk_analysis(user_ids)
            flash(f'AI analysis started for {len(user_ids)} pending users!', 'success')
        else:
            flash('No users pending analysis!', 'info')
        
        return redirect(url_for('dashboard'))

    @app.route('/migrate_db')
    def migrate_db():
        """Manual migration endpoint for testing"""
        try:
            from models import init_db
            init_db()
            flash('Database migration completed successfully!', 'success')
        except Exception as e:
            flash(f'Migration failed: {str(e)}', 'error')
        return redirect(url_for('dashboard'))

    # Excel processing helper functions
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
    
    @app.route('/analyze_all_pending')
    def analyze_all_pending():
        """Analyze all users with pending status (for admin)"""
        conn = get_db_connection()
        pending_users = conn.execute('''
            SELECT u.* FROM users u 
            LEFT JOIN user_analysis ua ON u.id = ua.user_id 
            WHERE ua.id IS NULL OR ua.eligibility_status = 'Pending'
            LIMIT 10
        ''').fetchall()
        conn.close()

        analyzed_count = 0
        for user in pending_users:
            try:
                analyze_loan_eligibility(user['id'])
                analyzed_count += 1
            except Exception as e:
                print(f"Failed to analyze user {user['id']}: {e}")

        flash(f'AI analysis completed for {analyzed_count} users!', 'success')
        return redirect(url_for('dashboard'))
    
