import google.generativeai as genai
import json
import re
import threading
import time
from config import Config
from models import get_db_connection, save_analysis_result, update_analysis_error
from utils import get_uploaded_documents, get_required_documents

# Configure Gemini API
try:
    genai.configure(api_key=Config.GEMINI_API_KEY)
    print("Gemini API configured successfully")
except Exception as e:
    print(f"Gemini API configuration failed: {e}")

def get_available_models():
    """List available models for debugging"""
    try:
        models = genai.list_models()
        available_models = [model.name for model in models]
        return available_models
    except Exception as e:
        print(f"Failed to list models: {e}")
        return []

def get_gemini_model():
    """Get the correct Gemini model with fallback"""
    try:
        # Try the newer model names first
        model_names = [
            'gemini-1.5-pro',
            'gemini-1.0-pro',
            'models/gemini-pro',
            'gemini-pro'
        ]
        
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(model_name)
                # Test with a simple prompt to verify the model works
                response = model.generate_content("Hello")
                return model
            except Exception as e:
                print(f"Model {model_name} failed: {e}")
                continue
        
        # If no model works, raise error
        raise Exception("No working Gemini model found. Available models: " + str(get_available_models()))
        
    except Exception as e:
        print(f"Failed to get Gemini model: {e}")
        raise e

def trigger_ai_analysis(user_id):
    """Trigger AI analysis in background thread"""
    if not Config.AUTO_ANALYSIS_ENABLED:
        return
    
    # Run analysis in background thread
    thread = threading.Thread(target=analyze_loan_eligibility, args=(user_id,))
    thread.daemon = True
    thread.start()

def analyze_loan_eligibility(user_id):
    """Main function to analyze loan eligibility using Gemini AI"""
    retry_count = 0
    max_retries = Config.AI_RETRY_ATTEMPTS
    
    while retry_count <= max_retries:
        try:
            # Add delay between retries to avoid rate limiting
            if retry_count > 0:
                time.sleep(2 ** retry_count)  # Exponential backoff: 2, 4, 8 seconds
            
            # Get user data
            conn = get_db_connection()
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            conn.close()
            
            if not user:
                print(f"User {user_id} not found for analysis")
                return {"error": "User not found"}
            
            user_data = dict(user)
            
            # Get uploaded documents
            uploaded_documents = get_uploaded_documents(user_id)
            
            # Create structured prompt data
            prompt_data = create_structured_prompt_data(user_data, uploaded_documents)
            
            # Call Gemini API
            analysis_result = call_gemini_api(prompt_data)
            
            # Save successful result
            save_analysis_result(
                user_id=user_id,
                eligibility_status=analysis_result.get('eligibility', 'Pending'),
                foir=analysis_result.get('foir_used'),
                ltv=analysis_result.get('ltv_used'),
                ai_summary=analysis_result.get('reasoning', ''),
                ai_queries='\n'.join(analysis_result.get('queries', [])),
                missing_docs='\n'.join(analysis_result.get('missing_documents', [])),
                risk_level=analysis_result.get('risk_level', 'Medium'),
                recommendation=analysis_result.get('recommendation', ''),
                retry_count=retry_count
            )
            
            return analysis_result
            
        except Exception as e:
            retry_count += 1
            error_msg = f"Attempt {retry_count}/{max_retries}: {str(e)}"
            print(f"AI Analysis Error for user {user_id}: {error_msg}")
            
            if retry_count <= max_retries:
                continue
            else:
                # Final failure - save error information
                update_analysis_error(user_id, error_msg, retry_count)
                return {"error": str(e)}

def create_structured_prompt_data(user_data, uploaded_documents):
    """Create structured data for AI prompt"""
    
    # Calculate basic metrics
    property_value = user_data.get('sale_deed_amount', 0)
    loan_amount = user_data.get('loan_amount', 0)
    ltv = (loan_amount / property_value * 100) if property_value > 0 else 0
    
    # Estimate age from experience (simplified)
    estimated_age = estimate_age_from_experience(user_data.get('total_experience', ''))
    
    # Document analysis
    required_docs = get_required_documents(user_data)
    uploaded_doc_types = [doc['document_type'] for doc in uploaded_documents]
    missing_docs = [doc for doc in required_docs if doc not in uploaded_doc_types]
    
    # Build structured data
    prompt_data = {
        "user_id": user_data['id'],
        "applicant_details": {
            "name": user_data['applicant_name'],
            "email": user_data['email_id'],
            "mobile": user_data.get('mobile_no', 'Not provided'),
            "estimated_age": estimated_age,
            "employment_type": classify_employment_type(user_data),
            "designation": user_data.get('designation', 'Not provided'),
            "department": user_data.get('department', 'Not provided'),
            "experience": user_data.get('total_experience', 'Not provided'),
            "job_since": user_data.get('job_since', 'Not provided'),
            "qualification": user_data.get('qualification', 'Not provided')
        },
        "loan_details": {
            "loan_amount": loan_amount,
            "tenure_months": user_data.get('tenure', 0),
            "tenure_years": user_data.get('tenure', 0) / 12,
            "property_type": user_data.get('property_type', 'Not specified'),
            "property_value": property_value,
            "ltv_calculated": ltv
        },
        "co_applicant_details": {
            "has_co_applicant": user_data['has_co_applicant'],
            "name": user_data.get('co_applicant_name', ''),
            "qualification": user_data.get('co_applicant_qualification', '')
        } if user_data['has_co_applicant'] else {},
        "documents_analysis": {
            "uploaded_count": len(uploaded_documents),
            "required_count": len(required_docs),
            "uploaded_documents": uploaded_doc_types,
            "missing_documents": missing_docs,
            "completion_percentage": (len(uploaded_doc_types) / len(required_docs) * 100) if required_docs else 0
        },
        "eligibility_rules": {
            "salaried": {
                "max_foir": Config.SALARIED_FOIR_MAX * 100,
                "max_age": Config.MAX_AGE_SALARIED,
                "max_tenure": Config.MAX_TENURE
            },
            "self_employed": {
                "max_foir": Config.SELF_EMPLOYED_FOIR_MAX * 100,
                "max_age": Config.MAX_AGE_SELF_EMPLOYED,
                "foir_plus_ltv_max": 140
            },
            "general": {
                "max_ltv": Config.LTV_THRESHOLD * 100,
                "min_document_completion": 80  # Minimum document completion percentage
            }
        }
    }
    
    return prompt_data

def call_gemini_api(prompt_data):
    """Call Gemini API with structured data"""
    try:
        model = get_gemini_model()
        
        # Create detailed prompt
        prompt = create_detailed_prompt(prompt_data)
        
        response = model.generate_content(prompt)
        return parse_gemini_response(response.text)
        
    except Exception as e:
        print(f"Gemini API call failed: {e}")
        # Return a fallback analysis if API fails
        return create_fallback_analysis(prompt_data)

def create_fallback_analysis(prompt_data):
    """Create a fallback analysis when AI is not available"""
    loan_amount = prompt_data['loan_details']['loan_amount']
    property_value = prompt_data['loan_details']['property_value']
    ltv = prompt_data['loan_details']['ltv_calculated']
    doc_completion = prompt_data['documents_analysis']['completion_percentage']
    
    # Simple rule-based fallback analysis
    if doc_completion < 50:
        eligibility = "Not Eligible"
        reasoning = "Insufficient documents uploaded for proper assessment"
    elif ltv > 75:
        eligibility = "Not Eligible"
        reasoning = f"LTV ratio {ltv:.1f}% exceeds maximum 75% threshold"
    elif doc_completion >= 80:
        eligibility = "Conditional"
        reasoning = "Documents appear complete, but manual income verification required"
    else:
        eligibility = "Pending"
        reasoning = "Insufficient data for automated analysis"
    
    return {
        "eligibility": eligibility,
        "foir_used": None,
        "ltv_used": ltv,
        "risk_level": "Medium",
        "reasoning": f"FALLBACK ANALYSIS: {reasoning}",
        "missing_documents": prompt_data['documents_analysis']['missing_documents'],
        "queries": ["Manual verification required due to AI service unavailability"],
        "recommendation": "Please verify income documents and property valuation manually"
    }

def create_detailed_prompt(prompt_data):
    """Create detailed prompt for Gemini"""
    
    prompt = f"""
    LOAN ELIGIBILITY ANALYSIS REQUEST

    Please analyze this loan application and provide a structured JSON response.

    APPLICANT DATA:
    {json.dumps(prompt_data, indent=2)}

    ANALYSIS INSTRUCTIONS:

    1. Evaluate eligibility based on:
       - FOIR (Fixed Obligation to Income Ratio) - estimate based on standard industry norms
       - LTV (Loan-to-Value) ratio
       - Document completeness
       - Employment stability
       - Age considerations

    2. Consider these rules:
       - Salaried: FOIR ≤ {prompt_data['eligibility_rules']['salaried']['max_foir']}%, Age ≤ {prompt_data['eligibility_rules']['salaried']['max_age']}
       - Self-employed: FOIR ≤ {prompt_data['eligibility_rules']['self_employed']['max_foir']}%, FOIR + LTV ≤ 140%
       - Maximum LTV: {prompt_data['eligibility_rules']['general']['max_ltv']}%

    3. IMPORTANT: Never show full Aadhaar numbers. Mask first 8 digits if mentioned.

    4. Return analysis in this exact JSON format:
    {{
        "eligibility": "Eligible/Not Eligible/Conditional",
        "foir_used": 55.5,
        "ltv_used": 62.5,
        "risk_level": "Low/Medium/High",
        "reasoning": "Detailed explanation of the decision",
        "missing_documents": ["Document1", "Document2"],
        "queries": ["Query question 1", "Query question 2"],
        "recommendation": "Overall recommendation text"
    }}

    5. For FOIR calculation, assume standard income estimates based on:
       - Designation and industry norms
       - Document completeness
       - Employment history

    Provide only the JSON response, no additional text.
    """
    
    return prompt

def parse_gemini_response(response_text):
    """Parse Gemini response and extract structured data"""
    try:
        # Clean the response text
        cleaned_text = response_text.strip()
        
        # Remove markdown code blocks if present
        cleaned_text = re.sub(r'```json\s*', '', cleaned_text)
        cleaned_text = re.sub(r'```\s*', '', cleaned_text)
        
        # Try to find JSON in the response
        json_match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
        if json_match:
            json_str = json_match.group()
            result = json.loads(json_str)
            
            # Validate required fields
            if 'eligibility' not in result:
                result['eligibility'] = 'Analysis Completed'
            if 'reasoning' not in result:
                result['reasoning'] = 'AI analysis completed'
            if 'queries' not in result:
                result['queries'] = []
            if 'missing_documents' not in result:
                result['missing_documents'] = []
                
            return result
        else:
            # Fallback for non-JSON responses
            return {
                "eligibility": "Analysis Completed",
                "reasoning": cleaned_text,
                "queries": ["Manual review recommended"],
                "missing_documents": [],
                "risk_level": "Medium",
                "recommendation": "Please review the AI analysis manually"
            }
            
    except json.JSONDecodeError as e:
        print(f"JSON parsing failed: {e}")
        return {
            "eligibility": "Analysis Error",
            "reasoning": f"JSON parsing failed: {str(e)}",
            "queries": ["Technical analysis error"],
            "missing_documents": [],
            "risk_level": "High",
            "recommendation": "Please retry analysis or check manually"
        }

def estimate_age_from_experience(experience_text):
    """Estimate age from experience (simplified)"""
    if not experience_text:
        return 30  # Default assumption
    
    # Extract years from experience text
    years_match = re.search(r'(\d+)\s*(years|yrs)', experience_text.lower())
    if years_match:
        experience_years = int(years_match.group(1))
        # Assume starting career at 22 + experience years
        return 22 + experience_years
    
    return 30  # Default fallback

def classify_employment_type(user_data):
    """Classify employment type based on user data"""
    designation = (user_data.get('designation') or '').lower()
    department = (user_data.get('department') or '').lower()
    
    # Self-employed indicators
    self_employed_keywords = ['business', 'proprietor', 'partner', 'entrepreneur', 'self employed']
    
    for keyword in self_employed_keywords:
        if keyword in designation or keyword in department:
            return 'Self-Employed'
    
    return 'Salaried'

def trigger_bulk_analysis(user_ids):
    """Trigger AI analysis for multiple users with delays to avoid rate limiting"""
    for i, user_id in enumerate(user_ids):
        trigger_ai_analysis(user_id)
        # Add delay between requests to avoid rate limiting
        if i < len(user_ids) - 1:  # Don't delay after the last one
            time.sleep(1)  # 1 second delay between requests