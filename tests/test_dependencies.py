# test_dependencies.py
import google.generativeai as genai
from pdf2image import convert_from_path
from PIL import Image
import pydantic
import numpy as np

print("✓ google-generativeai:", genai.__version__ if hasattr(genai, '__version__') else "installed")
print("✓ pdf2image: installed")
print("✓ Pillow:", Image.__version__)
print("✓ pydantic:", pydantic.__version__)
print("✓ numpy:", np.__version__)
print("\n✅ All dependencies installed!")