# src/validation/age_validator.py
"""
Age and DOB validation for appropriate query handling.
"""

from datetime import datetime, date
from dateutil.relativedelta import relativedelta
from typing import Dict, Optional, Tuple


class AgeValidator:
    """Validates age appropriateness for astrological queries."""
    
    # Age thresholds for different query types
    AGE_THRESHOLDS = {
        "marriage": {"min": 18, "max": 80, "typical_min": 21},
        "job": {"min": 16, "max": 70, "typical_min": 18},
        "children": {"min": 18, "max": 55, "typical_min": 22},
        "education": {"min": 5, "max": 40, "typical_min": 15},
        "business": {"min": 18, "max": 75, "typical_min": 25},
        "health": {"min": 0, "max": 120, "typical_min": 0},
        "career": {"min": 16, "max": 70, "typical_min": 18},
        "property": {"min": 21, "max": 80, "typical_min": 25},
        "foreign_travel": {"min": 10, "max": 90, "typical_min": 18},
    }
    
    @staticmethod
    def calculate_age(date_of_birth: str) -> Tuple[int, int, int]:
        """
        Calculate age from DOB.
        
        Returns: (years, months, days)
        """
        try:
            if isinstance(date_of_birth, str):
                dob = datetime.strptime(date_of_birth, "%Y-%m-%d").date()
            else:
                dob = date_of_birth
            
            today = date.today()
            
            if dob > today:
                return (-1, 0, 0)  # Future date
            
            delta = relativedelta(today, dob)
            return (delta.years, delta.months, delta.days)
            
        except Exception as e:
            print(f"[AGE_VALIDATOR] Error calculating age: {e}")
            return (-2, 0, 0)  # Sentinel: parse failure (distinct from future date -1 and genuine newborn)
    
    @staticmethod
    def validate_dob(date_of_birth: str) -> Dict:
        """
        Validate date of birth.
        
        Returns:
            {
                "valid": bool,
                "issue": str or None,
                "age_years": int,
                "age_months": int,
                "age_days": int
            }
        """
        years, months, days = AgeValidator.calculate_age(date_of_birth)

        # Parse failure (invalid format)
        if years == -2:
            return {
                "valid": False,
                "issue": "invalid_format",
                "message": "Your date of birth could not be read. Please ensure it is in YYYY-MM-DD format (e.g., 1990-07-15) and re-initialize your session.",
                "age_years": 0,
                "age_months": 0,
                "age_days": 0
            }

        # Future date
        if years < 0:
            return {
                "valid": False,
                "issue": "future_date",
                "message": "Date of birth is in the future. Please check your birth date.",
                "age_years": years,
                "age_months": months,
                "age_days": days
            }
        
        # Too young (less than 1 month)
        if years == 0 and months == 0 and days < 30:
            return {
                "valid": False,
                "issue": "infant",
                "message": f"The person is only {days} days old. Vedic astrology predictions are more meaningful for individuals who are at least a few years old.",
                "age_years": years,
                "age_months": months,
                "age_days": days
            }
        
        # Very young (less than 5 years)
        if years < 5:
            return {
                "valid": True,  # Valid but with warning
                "issue": "very_young",
                "message": f"The person is {years} years and {months} months old. Some life event predictions may not be immediately relevant.",
                "age_years": years,
                "age_months": months,
                "age_days": days,
                "warning": True
            }
        
        # Extremely old (unrealistic)
        if years > 120:
            return {
                "valid": False,
                "issue": "unrealistic_age",
                "message": f"The calculated age is {years} years, which seems unrealistic. Please verify the birth date.",
                "age_years": years,
                "age_months": months,
                "age_days": days
            }
        
        # Valid
        return {
            "valid": True,
            "issue": None,
            "message": None,
            "age_years": years,
            "age_months": months,
            "age_days": days
        }
    
    @staticmethod
    def is_query_appropriate(query_type: str, age_years: int, language: str = "en") -> Dict:
        """
        Check if query is age-appropriate.
        
        Args:
            query_type: Type of query (marriage, job, etc.)
            age_years: User's age in years
            language: Response language
        
        Returns:
            {
                "appropriate": bool,
                "reason": str,
                "message": str (polite response)
            }
        """
        if query_type not in AgeValidator.AGE_THRESHOLDS:
            return {"appropriate": True, "reason": None, "message": None}
        
        thresholds = AgeValidator.AGE_THRESHOLDS[query_type]
        min_age = thresholds["min"]
        max_age = thresholds["max"]
        typical_min = thresholds["typical_min"]
        
        # Too young
        if age_years < min_age:
            messages = {
                "en": f"Based on your age ({age_years} years), {query_type} related predictions may not be immediately relevant. Such life events typically become significant after {typical_min} years of age. However, I can provide insights about your chart's potential in this area for the future.",
                "hi-lat": f"Aapki umar ({age_years} saal) ko dekhte hue, {query_type} se related predictions abhi turant relevant nahi honge. Aisi life events typically {typical_min} saal ki umar ke baad meaningful hoti hain. Lekin main aapko future ke liye aapke chart ki potential ke baare mein bata sakta hoon."
            }
            
            return {
                "appropriate": False,
                "reason": "too_young",
                "message": messages.get(language, messages["en"]),
                "suggested_age": typical_min
            }
        
        # Too old (for certain events like first child)
        if age_years > max_age and query_type in ["children", "marriage"]:
            messages = {
                "en": f"Based on your age ({age_years} years), questions about {query_type} may need special consideration. I can provide insights based on your chart, but some traditional interpretations may not fully apply to your current life stage.",
                "hi-lat": f"Aapki umar ({age_years} saal) ko dekhte hue, {query_type} ke baare mein kuch special considerations hain. Main aapke chart ke basis par insights de sakta hoon, lekin kuch traditional interpretations aapki current life stage par puri tarah apply nahi hote."
            }
            
            return {
                "appropriate": True,  # Don't block, but provide context
                "reason": "age_consideration",
                "message": messages.get(language, messages["en"]),
                "warning": True
            }
        
        return {"appropriate": True, "reason": None, "message": None}
    
    @staticmethod
    def detect_query_type(query: str) -> Optional[str]:
        """
        Detect query type from user question.
        
        Returns: query_type or None
        """
        query_lower = query.lower()
        
        # Marriage keywords
        if any(word in query_lower for word in ["marriage", "marry", "shaadi", "shadi", "vivah", "wedding", "spouse", "husband", "wife"]):
            return "marriage"
        
        # Job/Career keywords
        if any(word in query_lower for word in ["job", "naukri", "employment", "career", "work", "profession", "occupation"]):
            return "job"
        
        # Children keywords
        if any(word in query_lower for word in ["child", "children", "baby", "pregnancy", "bachha", "bacche", "santan", "offspring"]):
            return "children"
        
        # Education keywords
        if any(word in query_lower for word in ["education", "study", "studies", "padhai", "school", "college", "exam", "degree"]):
            return "education"
        
        # Business keywords
        if any(word in query_lower for word in ["business", "vyapar", "vyapaar", "entrepreneur", "startup"]):
            return "business"
        
        # Property keywords
        if any(word in query_lower for word in ["property", "house", "ghar", "real estate", "land", "plot"]):
            return "property"
        
        return None