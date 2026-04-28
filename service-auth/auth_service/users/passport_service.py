# passport_service.py - With Tesseract check and debugging
import tempfile
import urllib.request
import os
import sys
from datetime import datetime
from difflib import SequenceMatcher
import subprocess

from passporteye import read_mrz
import pytesseract


def check_tesseract_installed():
    """Check if Tesseract is properly installed and accessible"""
    try:
        # Check if tesseract binary exists
        result = subprocess.run(['which', 'tesseract'], capture_output=True, text=True)
        if result.returncode != 0:
            print("[MRZ] ERROR: Tesseract not found in PATH")
            print("[MRZ] Please install: apt-get install tesseract-ocr")
            return False
        
        print(f"[MRZ] Tesseract found at: {result.stdout.strip()}")
        
        # Check version
        version = subprocess.run(['tesseract', '--version'], capture_output=True, text=True)
        print(f"[MRZ] Tesseract version: {version.stdout.split(chr(10))[0]}")
        
        # Check available languages
        langs = subprocess.run(['tesseract', '--list-langs'], capture_output=True, text=True)
        print(f"[MRZ] Available languages: {langs.stdout.strip()}")
        
        return True
    except Exception as e:
        print(f"[MRZ] Error checking tesseract: {e}")
        return False


def download_image_temp(url: str) -> str:
    """Download a Cloudinary URL to a temp file, return local path."""
    suffix = '.jpg'
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
        urllib.request.urlretrieve(url, f.name)
        print(f"[MRZ] Image downloaded to: {f.name} ({os.path.getsize(f.name)} bytes)")
        return f.name


def extract_mrz_data(image_url: str) -> dict | None:
    """
    Download passport image and extract MRZ fields.
    Returns a dict or None if extraction fails.
    """
    local_path = None
    
    try:
        # Check tesseract first
        if not check_tesseract_installed():
            print("[MRZ] ERROR: Tesseract is required but not installed")
            return None
        
        # Download image
        local_path = download_image_temp(image_url)
        
        # Configure pytesseract path if needed
        tesseract_path = subprocess.run(['which', 'tesseract'], capture_output=True, text=True).stdout.strip()
        if tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = tesseract_path
        
        # Try to read MRZ
        print("[MRZ] Attempting to read MRZ...")
        mrz = read_mrz(local_path)
        
        if mrz is None:
            print("[MRZ] read_mrz returned None")
            return None
        
        # Extract data
        d = mrz.to_dict()
        print(f"[MRZ] Successfully extracted data:")
        for key, value in d.items():
            print(f"  {key}: {value}")
        
        return {
            'surname': d.get('surname', ''),
            'name': d.get('name', ''),
            'number': d.get('number', ''),
            'date_of_birth': d.get('date_of_birth', ''),
            'expiry_date': d.get('expiry_date', ''),
            'nationality': d.get('nationality', ''),
            'sex': d.get('sex', ''),
        }
        
    except Exception as e:
        print(f"[MRZ] Extraction error: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # Cleanup temp file
        if local_path and os.path.exists(local_path):
            try:
                os.unlink(local_path)
            except:
                pass


def _normalize(s: str) -> str:
    """Normalize string for comparison"""
    return (s or '').upper().strip().replace('-', ' ').replace('<', ' ')


def _fuzzy(a: str, b: str, threshold: float = 0.82) -> bool:
    """Fuzzy string matching"""
    if not a or not b:
        return True
    return SequenceMatcher(None, _normalize(a), _normalize(b)).ratio() >= threshold


def _parse_mrz_date(yymmdd: str):
    """Convert YYMMDD → date"""
    if not yymmdd:
        return None
    try:
        return datetime.strptime(yymmdd, '%y%m%d').date()
    except (ValueError, TypeError):
        return None


def validate_mrz_against_person(person, mrz_data: dict) -> tuple[bool, list[str]]:
    """
    Compare MRZ-extracted fields against the Personne instance fields.
    Returns (is_valid: bool, errors: list[str])
    """
    errors = []

    # --- Name checks (with fuzzy matching for Arabic/French variations) ---
    if person.nom and mrz_data.get('surname'):
        if not _fuzzy(person.nom, mrz_data['surname']):
            errors.append(
                f"Nom ne correspond pas : BD='{person.nom}' / MRZ='{mrz_data['surname']}'"
            )

    if person.prenom and mrz_data.get('name'):
        if not _fuzzy(person.prenom, mrz_data['name']):
            errors.append(
                f"Prénom ne correspond pas : BD='{person.prenom}' / MRZ='{mrz_data['name']}'"
            )

    # --- Passport number ---
    if person.num_passport and mrz_data.get('number'):
        if _normalize(person.num_passport) != _normalize(mrz_data['number']):
            errors.append(
                f"Numéro passport ne correspond pas : BD='{person.num_passport}' / MRZ='{mrz_data['number']}'"
            )

    # --- Date of birth ---
    if person.date_naissance and mrz_data.get('date_of_birth'):
        mrz_dob = _parse_mrz_date(mrz_data['date_of_birth'])
        if mrz_dob and person.date_naissance != mrz_dob:
            errors.append(
                f"Date de naissance ne correspond pas : BD='{person.date_naissance}' / MRZ='{mrz_dob}'"
            )

    # --- Expiry date ---
    if mrz_data.get('expiry_date'):
        expiry = _parse_mrz_date(mrz_data['expiry_date'])
        if expiry:
            if expiry < datetime.today().date():
                errors.append(f"Passport expiré le {expiry}")
            if not person.date_exp_passport:
                person.date_exp_passport = expiry

    # --- Sex ---
    if person.sexe and mrz_data.get('sex'):
        mrz_sex = mrz_data['sex'].upper()
        model_sex = 'M' if person.sexe == 'homme' else 'F'
        if mrz_sex not in ('', '<') and mrz_sex != model_sex:
            errors.append(f"Sexe ne correspond pas : BD='{person.sexe}' / MRZ='{mrz_sex}'")

    return len(errors) == 0, errors